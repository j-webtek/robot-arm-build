"""Retained native observations -> settings -> actual diagnostic pixels.

This is an application-owned result lifecycle, not a provider or an admission
API. The caller supplies original preparations and independently audited M1
hashes. It still owns runtime-pair review, campaign admission and publication.
No method activates hardware, creates a native working directory, or infers a
known campaign / physical-stage PASS from a successfully retained image.
"""

from __future__ import annotations

from contextlib import ExitStack
from dataclasses import replace
import json
import math
from pathlib import Path
import re
import threading
import time
from typing import Any

from .camera_capture_dataset import (
    MAX_DATASET_BYTES,
    DatasetQuotas,
    FramePlan,
    PreviewTransform,
)
from .physical_camera_configuration import (
    PhysicalCameraCapabilities,
    PhysicalCameraReadback,
    StagedPhysicalCameraConfiguration,
    compare_physical_camera_readback,
    derive_physical_camera_capabilities,
    stage_physical_camera_configuration,
    _verified_observation,
)
from .physical_camera_selection import PhysicalCameraSelection
from .physical_native_camera_campaign import PhysicalNativeCameraCampaign
from .physical_camera_activation_campaign import PhysicalCameraActivationCampaign
from .camera_activation_campaign_evidence import (
    CameraActivationArtifact,
    MAX_CAMERA_ACTIVATION_CAMPAIGN_BYTES,
)
from .camera_capture_checksum import (
    CameraCaptureChecksum,
    MAX_BYTES as MAX_CHECKSUM_BYTES,
    verify_capture_checksum,
)
from rocell.providers.windows.native_camera_activation_registration import (
    NativeCameraActivationRuntime,
    PreparedOwnedNativeActivation,
)
from rocell.providers.windows.native_camera_activation_expectation import (
    CameraActivationExpectation,
)
from .physical_onboarding_durability import safe_root
from .windows_camera_capture_ingest import (
    DerivedCameraPreview,
    NativeCaptureIngestReceipt,
    ingest_windows_capture,
    prepare_windows_camera_ingest,
    verify_windows_capture_ingest,
)
from .wizard_diagnostic_coordinator import source_fingerprint
from .wizard_diagnostic_export import _directory_guard
from rocell.providers.windows.camera_worker_client import (
    CameraCampaignBudget,
    CameraControlSetting,
    NativeFrameArtifact,
    validate_capture_artifacts,
)
from rocell.providers.windows.native_camera_capture_protocol import local_capture_path
from rocell.providers.windows.native_camera_capture_registration import (
    NativeCameraCaptureRuntimeRegistration,
    PreparedOwnedNativeCapture,
)
from rocell.providers.windows.native_camera_protocol import canonical, digest
from rocell.providers.windows.native_camera_registration import (
    NativeCameraRuntimeRegistration,
    PreparedOwnedNativeProbe,
)
from rocell.providers.windows.owned_native_camera_evidence import (
    OwnedNativeCameraRunEvidence,
)
from rocell.providers.windows.owned_worker_process import decode_owned_json


SCHEMA = "rocell.physical_camera_capture_workflow.v1"
RETENTION_TIMEOUT_MS = 120_000
MAX_PREVIEW_BYTES = 2 * 1024 * 1024
MAX_RETENTION_ATTEMPTS = 128
_CODE = re.compile(r"[A-Z][A-Z0-9_]{0,95}\Z")


class PhysicalCameraCaptureWorkflowError(ValueError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _require(ok: bool, code: str) -> None:
    if not ok:
        raise PhysicalCameraCaptureWorkflowError(code)


def _copy(value: Any, *, maximum: int = 1024 * 1024) -> Any:
    # Existing evidence schemas own validation; this is detached JSON, not a
    # competing report codec. The combined private diagnostic has its own cap.
    payload = canonical(value)
    _require(len(payload) <= maximum, "WORKFLOW_DIAGNOSTIC_BYTE_LIMIT")
    return json.loads(payload)


class PhysicalCameraCaptureWorkflow:
    """Inert context; explicit file-only capture retention; bounded cached view.

    `accept_*` arguments are trusted *references* from the service/M1 boundary,
    not browser inputs. A structurally self-consistent record is not its own
    provenance. Modeled physical-shaped evidence belongs only in unit tests.
    """

    def __init__(
        self,
        workspace: Path,
        assigned_parent: Path,
        *,
        source_sha256: str,
        cell_id: str,
        session_id: str,
        selection: PhysicalCameraSelection,
        probe_runtime: NativeCameraRuntimeRegistration | NativeCameraActivationRuntime,
        capture_runtime: (
            NativeCameraCaptureRuntimeRegistration | NativeCameraActivationRuntime
        ),
        activation_expectation: CameraActivationExpectation | None = None,
    ) -> None:
        self._activation = type(probe_runtime) is NativeCameraActivationRuntime
        _require(
            (
                self._activation
                and type(capture_runtime) is NativeCameraActivationRuntime
                and type(activation_expectation) is CameraActivationExpectation
                and probe_runtime.to_dict()["purpose"] == "probe"
                and capture_runtime.to_dict()["purpose"] == "capture"
            )
            or (
                type(probe_runtime) is NativeCameraRuntimeRegistration
                and type(capture_runtime) is NativeCameraCaptureRuntimeRegistration
                and activation_expectation is None
            ),
            "EXACT_PURPOSE_RUNTIME_PAIR_REQUIRED",
        )
        campaign_type = (
            PhysicalCameraActivationCampaign
            if self._activation
            else PhysicalNativeCameraCampaign
        )
        native_arguments: dict[str, Any] = {"runtime": probe_runtime}
        if self._activation:
            native_arguments["expectation"] = activation_expectation
        probe = campaign_type(
            workspace,
            assigned_parent,
            source_sha256=source_sha256,
            cell_id=cell_id,
            session_id=session_id,
            selection=selection,
            **native_arguments,
        )
        self._context = canonical(probe.plan())
        self._capture_runtime = type(capture_runtime)(capture_runtime.payload)
        capture = self._capture_runtime.to_dict()
        _require(
            capture["workspace"] == str(workspace)
            and capture["source_sha256"] == source_sha256,
            "CAPTURE_RUNTIME_CONTEXT_MISMATCH",
        )
        self._state_lock = threading.RLock()
        self._operation_lock = threading.Lock()
        # Staged publication copies share a bounded, non-replacing one-use
        # retention ledger. Discarding a failed publication must not retry I/O.
        self._claims_lock = threading.Lock()
        self._claims: set[str] = set()
        self._generation = 0
        self._capabilities: PhysicalCameraCapabilities | None = None
        self._configuration: StagedPhysicalCameraConfiguration | None = None
        self._readback: PhysicalCameraReadback | None = None
        self._preview: DerivedCameraPreview | None = None
        self._last_frame: dict[str, Any] | None = None
        self._status = "HELD"
        self._error: dict[str, str] | None = None
        self._diagnostics: dict[str, Any] = {}

    def _plan_context(self) -> dict[str, Any]:
        return _copy_from_bytes(self._context)

    def staged_copy(self) -> PhysicalCameraCaptureWorkflow:
        """Detached candidate state; does not publish or repeat file operations."""
        with self._state_lock:
            data = self._plan_context()
            result = type(self)(
                Path(data["workspace"]),
                Path(data["assigned_parent_directory"]),
                source_sha256=data["source_sha256"],
                cell_id=data["cell_id"],
                session_id=data["session_id"],
                selection=PhysicalCameraSelection(canonical(data["selection"])),
                probe_runtime=(
                    NativeCameraActivationRuntime
                    if self._activation
                    else NativeCameraRuntimeRegistration
                )(canonical(data["runtime"])),
                capture_runtime=self._capture_runtime,
                activation_expectation=(
                    CameraActivationExpectation(canonical(data["expectation"]))
                    if self._activation
                    else None
                ),
            )
            result._capabilities = self._capabilities
            result._configuration = self._configuration
            result._readback = self._readback
            result._preview = self.last_preview()
            result._last_frame = _copy(self._last_frame)
            result._diagnostics = self._diagnostic_copy()
            result._status, result._error = self._status, _copy(self._error)
            result._claims, result._claims_lock = self._claims, self._claims_lock
            return result

    def _clear_capture(self) -> None:
        self._generation += 1
        self._readback = self._preview = self._last_frame = None
        self._status, self._error = "HELD", None

    def invalidate(self) -> None:
        """Withdraw all current observations; keep only historical diagnostics."""
        with self._state_lock:
            self._clear_capture()
            self._capabilities = self._configuration = None

    def _failed(self, error: BaseException) -> None:
        code = getattr(error, "code", None)
        if type(code) is not str or _CODE.fullmatch(code) is None:
            code = "CAMERA_CAPTURE_WORKFLOW_FAILED"
        with self._state_lock:
            self._status = "HELD"
            self._preview = self._last_frame = None
            self._error = {"code": code}
            self._diagnostics["error"] = dict(self._error)

    def _check_preparation(
        self,
        prepared: (
            PreparedOwnedNativeProbe
            | PreparedOwnedNativeCapture
            | PreparedOwnedNativeActivation
        ),
        campaign: PhysicalNativeCameraCampaign | PhysicalCameraActivationCampaign,
    ) -> None:
        data, request = campaign.plan(), prepared.admission_request.to_dict()
        context = self._plan_context()
        working = Path(context["assigned_parent_directory"]) / (
            "native-camera-" + request["attempt_id"]
        )
        _require(
            prepared.runtime.to_dict() == data["runtime"]
            and request["source_sha256"] == context["source_sha256"]
            and request["session_id"] == context["session_id"]
            and request["selected_identity_sha256"]
            == context["selected_identity_sha256"]
            and request["operation_sha256"] == digest(canonical(data))
            and prepared.camera_plan.request.binding
            == PhysicalCameraSelection(canonical(context["selection"])).binding
            and prepared.to_dict()["working_directory"] == str(working),
            "ORIGINAL_NATIVE_PREPARATION_CONTEXT_MISMATCH",
        )

    def accept_probe(
        self,
        evidence: OwnedNativeCameraRunEvidence | tuple[CameraActivationArtifact, ...],
        *,
        expected_preparation: PreparedOwnedNativeProbe | PreparedOwnedNativeActivation,
        expected_evidence_sha256: str,
        expected_supervision_sha256: str | None = None,
    ) -> PhysicalCameraCapabilities:
        _require(self._operation_lock.acquire(False), "WORKFLOW_OPERATION_ACTIVE")
        try:
            with self._state_lock:
                self.invalidate()
                generation = self._generation
            _require(
                type(expected_preparation)
                is (
                    PreparedOwnedNativeActivation
                    if self._activation
                    else PreparedOwnedNativeProbe
                ),
                "EXACT_NATIVE_PROBE_PREPARATION_REQUIRED",
            )
            prepared = type(expected_preparation)(expected_preparation.payload)
            self._check_preparation(
                prepared, self._restore_campaign(self._plan_context())
            )
            checked = _verified_observation(
                evidence,
                prepared=prepared,
                expected_evidence_sha256=expected_evidence_sha256,
                expected_supervision_sha256=expected_supervision_sha256,
            )
            with self._state_lock:
                self._diagnostics = {"probe": checked.to_dict()}
            capabilities = derive_physical_camera_capabilities(
                evidence,
                expected_preparation=prepared,
                expected_evidence_sha256=expected_evidence_sha256,
                expected_source_sha256=self._plan_context()["source_sha256"],
                expected_supervision_sha256=expected_supervision_sha256,
            )
            with self._state_lock:
                _require(generation == self._generation, "WORKFLOW_CONTEXT_INVALIDATED")
                self._capabilities, self._status = capabilities, "PROBE_ACCEPTED"
                self._diagnostics["capabilities"] = capabilities.to_dict()
            return PhysicalCameraCapabilities(capabilities.payload)
        except BaseException as error:
            self._failed(error)
            raise
        finally:
            self._operation_lock.release()

    def stage_settings(
        self,
        mode_choice_id: str,
        controls: tuple[CameraControlSetting, ...],
        *,
        expected_capabilities_sha256: str,
    ) -> StagedPhysicalCameraConfiguration:
        _require(self._operation_lock.acquire(False), "WORKFLOW_OPERATION_ACTIVE")
        try:
            with self._state_lock:
                self._clear_capture()
                self._configuration = None
                _require(
                    self._capabilities is not None, "RETAINED_PHYSICAL_PROBE_REQUIRED"
                )
                assert self._capabilities is not None
                data = self._plan_context()
                candidate = stage_physical_camera_configuration(
                    self._capabilities,
                    mode_choice_id,
                    controls,
                    expected_capabilities_sha256=expected_capabilities_sha256,
                    expected_source_sha256=data["source_sha256"],
                    expected_session_id=data["session_id"],
                    expected_selected_identity_sha256=data["selected_identity_sha256"],
                )
                self._configuration, self._status = candidate, "SETTINGS_STAGED"
                self._diagnostics["configuration"] = candidate.to_dict()
                return StagedPhysicalCameraConfiguration(candidate.payload)
        except BaseException as error:
            self._failed(error)
            raise
        finally:
            self._operation_lock.release()

    def capture_plan(
        self,
        *,
        budget: CameraCampaignBudget,
        configuration_verification: bool = False,
        sealed_configuration_capture: bool = False,
    ) -> dict[str, Any]:
        """Pure plan; the stage-5 profile is distinct from stage-6 freshness.

        Selecting a profile does not issue a permit, apply settings or satisfy
        stage policy. Legacy capture plans do not acquire this new profile.
        """
        _require(
            type(configuration_verification) is bool
            and (not configuration_verification or self._activation),
            "EXACT_CONFIGURATION_CAPTURE_PROFILE_REQUIRED",
        )
        _require(
            type(sealed_configuration_capture) is bool
            and (not sealed_configuration_capture or configuration_verification),
            "EXACT_SEALED_CONFIGURATION_PROFILE_REQUIRED",
        )
        with self._state_lock:
            _require(
                self._configuration is not None, "REVIEWED_PHYSICAL_SETTINGS_REQUIRED"
            )
            assert self._configuration is not None
            config, data = self._configuration, self._plan_context()
            campaign_type = (
                PhysicalCameraActivationCampaign
                if self._activation
                else PhysicalNativeCameraCampaign
            )
            native_arguments: dict[str, Any] = {"runtime": self._capture_runtime}
            if self._activation:
                native_arguments["expectation"] = CameraActivationExpectation(
                    canonical(data["expectation"])
                )
                native_arguments["configuration_verification"] = (
                    configuration_verification
                )
                native_arguments["sealed_configuration_capture"] = (
                    sealed_configuration_capture
                )
            return campaign_type(
                Path(data["workspace"]),
                Path(data["assigned_parent_directory"]),
                source_sha256=data["source_sha256"],
                cell_id=data["cell_id"],
                session_id=data["session_id"],
                selection=PhysicalCameraSelection(canonical(data["selection"])),
                mode=config.mode,
                controls=config.controls,
                budget=budget,
                **native_arguments,
            ).plan()

    def accept_capture(
        self,
        evidence: OwnedNativeCameraRunEvidence | tuple[CameraActivationArtifact, ...],
        *,
        expected_preparation: (
            PreparedOwnedNativeCapture | PreparedOwnedNativeActivation
        ),
        expected_evidence_sha256: str,
        expected_settings_epoch: str,
        cancellation: threading.Event,
        deadline_ns: int | None = None,
        expected_supervision_sha256: str | None = None,
        configuration_verification: bool = False,
        capture_reference_request_key: str | None = None,
        capture_checksum: CameraCaptureChecksum | None = None,
    ) -> NativeCaptureIngestReceipt | None:
        """One post-capture file action, never renewal of an expired native permit.

        Full native diagnostics/readback survive faults. Only clean matching
        readback reaches files. The fixed retention deadline covers source reads,
        hash/ingestion/content checks; synchronous primitives cannot be forcibly
        interrupted, so their late returns are denied before current publication.
        """
        _require(self._operation_lock.acquire(False), "WORKFLOW_OPERATION_ACTIVE")
        started = time.monotonic_ns()
        try:
            with self._state_lock:
                self._clear_capture()
                generation = self._generation
                config = self._configuration
                # A staged copy may carry an earlier capture's historical
                # reference. Do not attach it to this new retention attempt.
                self._diagnostics.pop("capture_reference_candidate", None)
                self._diagnostics.pop("capture_checksum", None)
            _require(type(cancellation) is threading.Event, "CANCELLATION_REQUIRED")
            fixed_deadline = started + RETENTION_TIMEOUT_MS * 1_000_000
            _require(
                deadline_ns is None
                or type(deadline_ns) is int
                and 0 < deadline_ns < 2**63,
                "EXACT_RETENTION_DEADLINE_REQUIRED",
            )
            deadline = (
                fixed_deadline
                if deadline_ns is None
                else min(fixed_deadline, deadline_ns)
            )

            def check() -> None:
                _require(not cancellation.is_set(), "CANCELLED")
                _require(time.monotonic_ns() < deadline, "RETENTION_TIMED_OUT")
                with self._state_lock:
                    _require(
                        self._generation == generation, "WORKFLOW_CONTEXT_INVALIDATED"
                    )

            def cancelled() -> bool:
                check()
                return False

            check()
            _require(
                capture_checksum is None
                or (
                    type(capture_checksum) is CameraCaptureChecksum
                    and self._activation
                    and configuration_verification is True
                    and capture_reference_request_key is not None
                ),
                "EXACT_RETAINED_CAPTURE_CHECKSUM_REQUIRED",
            )
            _require(
                capture_reference_request_key is None
                or (
                    self._activation
                    and configuration_verification is True
                    and type(capture_reference_request_key) is str
                    and re.fullmatch(
                        r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}",
                        capture_reference_request_key,
                    )
                    is not None
                ),
                "EXACT_CAPTURE_REFERENCE_REQUEST_REQUIRED",
            )
            _require(
                type(expected_preparation)
                is (
                    PreparedOwnedNativeActivation
                    if self._activation
                    else PreparedOwnedNativeCapture
                ),
                "EXACT_NATIVE_CAPTURE_PREPARATION_REQUIRED",
            )
            _require(
                config is not None and config.settings_epoch == expected_settings_epoch,
                "EXACT_STAGED_SETTINGS_REQUIRED",
            )
            assert config is not None
            prepared = type(expected_preparation)(expected_preparation.payload)
            request = prepared.camera_plan.request
            campaign = self._restore_campaign(
                self.capture_plan(
                    budget=request.budget,
                    configuration_verification=configuration_verification,
                    sealed_configuration_capture=capture_checksum is not None,
                )
            )
            self._check_preparation(prepared, campaign)
            checked = _verified_observation(
                evidence,
                prepared=prepared,
                expected_evidence_sha256=expected_evidence_sha256,
                expected_supervision_sha256=expected_supervision_sha256,
            )
            with self._claims_lock:
                _require(
                    request.campaign_id not in self._claims,
                    "CAPTURE_RETENTION_ALREADY_ATTEMPTED",
                )
                _require(
                    len(self._claims) < MAX_RETENTION_ATTEMPTS,
                    "RETENTION_ATTEMPT_LIMIT",
                )
                self._claims.add(request.campaign_id)
            with self._state_lock:
                self._diagnostics.update(capture=checked.to_dict())
                self._diagnostics.pop("ingest", None)
                self._diagnostics.pop("error", None)
            if capture_checksum is not None:
                capture_checksum = verify_capture_checksum(
                    capture_checksum.payload,
                    evidence=evidence,
                    expected_request_key=capture_reference_request_key,
                    expected_sha256=capture_checksum.sha256,
                )
                _require(
                    capture_checksum.to_dict()["status"] == "CAPTURE_BYTES_HASHED",
                    "ORIGINAL_CAPTURE_CHECKSUM_NOT_SUCCESSFUL",
                )
                with self._state_lock:
                    self._diagnostics["capture_checksum"] = dict(
                        document=capture_checksum.to_dict(),
                        sha256=capture_checksum.sha256,
                        retention="M1_ATTEMPT_CHECKSUM_JOINED_BY_ORIGINAL_DISPATCH",
                        original_stage_record_retained=False,
                    )
            readback = compare_physical_camera_readback(
                config,
                evidence,
                expected_preparation=prepared,
                expected_capture_evidence_sha256=expected_evidence_sha256,
                expected_settings_epoch=expected_settings_epoch,
                expected_supervision_sha256=expected_supervision_sha256,
            )
            with self._state_lock:
                self._diagnostics["readback"] = readback.to_dict()
                check()
                self._readback = readback
            check()
            if (
                readback.to_dict()["status"]
                != "REQUESTED_SETTINGS_OBSERVED_UNQUALIFIED"
            ):
                return None

            data = self._plan_context()
            parent = Path(data["assigned_parent_directory"])
            capture = (
                parent
                / ("native-camera-" + request.campaign_id)
                / ("capture-" + request.campaign_id)
            )
            datasets = parent / "capture-datasets"
            _require(
                request.output_directory == str(capture),
                "EXACT_ORIGINAL_CAPTURE_PATH_REQUIRED",
            )

            def current_source() -> None:
                check()
                _require(
                    source_fingerprint(Path(data["workspace"]))
                    == data["source_sha256"],
                    "WORKSPACE_SOURCE_CHANGED",
                )
                check()

            current_source()
            # Own exact original ancestors across raw validation, ingestion and
            # final verification. No helper/input-directory creation is allowed.
            with ExitStack() as guards:
                guards.enter_context(_directory_guard(safe_root(parent)))
                guards.enter_context(_directory_guard(safe_root(capture)))
                check()
                raw = checked.raw_native_receipt
                _require(raw is not None, "EXACT_NATIVE_CAPTURE_BODY_REQUIRED")
                typed = validate_capture_artifacts(raw, request=request)
                check()
                if capture_checksum is not None:
                    # This digest existed before the original terminal seal.
                    # Reject changed pixels before creating any dataset, rather
                    # than treating today's measured digest as its expected one.
                    _require(
                        typed.frames
                        == (
                            NativeFrameArtifact(**capture_checksum.to_dict()["frame"]),
                        ),
                        "CAPTURE_PIXELS_DIFFER_FROM_SEALED_CHECKSUM",
                    )
                if not datasets.exists():
                    datasets.mkdir()  # exact fixed child under the pinned assigned parent
                guards.enter_context(_directory_guard(safe_root(datasets)))
                assert request.mode is not None
                mode = request.mode
                # Largest exact-aspect-ratio preview <=640 per edge, never an
                # upscale. An irreducible huge ratio cannot silently be cropped.
                divisor = math.gcd(mode.width, mode.height)
                unit_w, unit_h = mode.width // divisor, mode.height // divisor
                scale = min(divisor, 640 // max(unit_w, unit_h))
                _require(scale >= 1, "EXACT_ASPECT_PREVIEW_UNAVAILABLE")
                preview = PreviewTransform(
                    0,
                    0,
                    mode.width,
                    mode.height,
                    unit_w * scale,
                    unit_h * scale,
                    maximum_bytes=MAX_PREVIEW_BYTES,
                )
                frames = tuple(
                    FramePlan(
                        f"frame-{index:06d}",
                        preview=(
                            preview if index == request.budget.max_frames - 1 else None
                        ),
                    )
                    for index in range(request.budget.max_frames)
                )
                plan = prepare_windows_camera_ingest(
                    request,
                    capture_directory=capture,
                    dataset_root=datasets,
                    source_sha256=data["source_sha256"],
                    settings_epoch=expected_settings_epoch,
                    domain="PHYSICAL_UNVERIFIED",
                    frames=frames,
                    quotas=DatasetQuotas(
                        frames=request.budget.max_frames,
                        frame_bytes=request.budget.max_frame_bytes,
                        # Native and preview bytes share the existing finite
                        # dataset ceiling. No component cap is silently raised.
                        total_bytes=min(
                            MAX_DATASET_BYTES,
                            request.budget.max_total_bytes + MAX_PREVIEW_BYTES,
                        ),
                    ),
                    retention_timeout_ms=RETENTION_TIMEOUT_MS,
                )
                check()
                result = ingest_windows_capture(
                    request, typed, plan=plan, cancelled=cancelled
                )
                # Preserve fully returned bytes even if a final Stop/source/
                # deadline/guard-exit failure makes them historical-only.
                with self._state_lock:
                    self._diagnostics["ingest"] = result.to_dict()
                check()
                _require(
                    result.envelope_path.parent.parent == datasets
                    and re.fullmatch(
                        r"ingest-[0-9a-f]{32}", result.envelope_path.parent.name
                    )
                    is not None
                    and result.envelope_path.name == "ingest-receipt.json"
                    and result.dataset.path.parent == result.envelope_path.parent,
                    "RETAINED_DATASET_OUTSIDE_ORIGINAL_STORE",
                )
                verified = verify_windows_capture_ingest(
                    result.to_dict(),
                    expected_source_sha256=data["source_sha256"],
                    expected_settings_epoch=expected_settings_epoch,
                    expected_campaign_id=request.campaign_id,
                    expected_endpoint_sha256=request.binding.endpoint_sha256,
                )
                check()
                _require(
                    verified.content_verified and result.latest_preview is not None,
                    "CONTENT_AND_PREVIEW_REQUIRED",
                )
                if capture_reference_request_key is not None:
                    from .camera_capture_reference import build_capture_reference
                    from .camera_operating_evidence_preflight import (
                        CameraNativeEvidenceSubject,
                    )

                    _require(
                        len(typed.frames) == 1
                        and result.latest_preview is not None
                        and typed.frames[0].sha256
                        == result.latest_preview.native_sha256,
                        "EXACT_CAPTURE_TIME_PIXEL_REFERENCE_REQUIRED",
                    )
                    candidate = build_capture_reference(
                        CameraNativeEvidenceSubject(
                            prepared,
                            evidence,
                            expected_evidence_sha256,
                            expected_supervision_sha256,
                        ),
                        configuration_payload=config.payload,
                        expected_settings_epoch=expected_settings_epoch,
                        request_key=capture_reference_request_key,
                        frame=typed.frames[0],
                        manifest_sha256=result.dataset.manifest_sha256,
                        ingest_envelope_sha256=result.envelope_sha256,
                    )
                    # Construct only from this completed ingestion, never from
                    # a later file read or launch-log import. This is retained
                    # diagnostic data pending a separate original-store writer.
                    # A late failure preserves the candidate but withholds media.
                    with self._state_lock:
                        self._diagnostics["capture_reference_candidate"] = dict(
                            document=candidate.to_dict(),
                            sha256=candidate.sha256,
                            retention="LAUNCH_DIAGNOSTIC_ONLY_NOT_M1_ORIGINAL",
                        )
                    check()
                current_source()
            check()  # including pin/guard cleanup time; no success before exits
            assert result.latest_preview is not None
            latest = result.latest_preview
            with self._state_lock:
                check()
                self._preview = replace(latest, transform=replace(latest.transform))
                self._last_frame = {
                    "image_id": None,
                    "attempt_id": request.campaign_id,
                    "frame_index": request.budget.max_frames - 1,
                    "preview_sha256": latest.png_sha256,
                    "native_frame_sha256": latest.native_sha256,
                    "manifest_sha256": result.dataset.manifest_sha256,
                    "settings_epoch": expected_settings_epoch,
                    "endpoint_sha256": request.binding.endpoint_sha256,
                    "capture_evidence_sha256": expected_evidence_sha256,
                    "provenance": "DERIVED_PREVIEW_OF_RETAINED_PHYSICAL_YUY2",
                    "frame_content_verified": True,
                    "live": False,
                }
                self._status = "CONTENT_VERIFIED"
            return result
        except BaseException as error:
            self._failed(error)
            raise
        finally:
            self._operation_lock.release()

    def view(self) -> dict[str, Any]:
        with self._state_lock:
            data = self._plan_context()
            return {
                "schema": SCHEMA,
                "binding": {
                    "source_sha256": data["source_sha256"],
                    "cell_id": data["cell_id"],
                    "session_id": data["session_id"],
                    "selected_identity_sha256": data["selected_identity_sha256"],
                    "probe_runtime_sha256": digest(canonical(data["runtime"])),
                    "capture_runtime_sha256": self._capture_runtime.registration_sha256,
                },
                "status": self._status,
                "configuration": {
                    "capabilities": (
                        None
                        if self._capabilities is None
                        else self._capabilities.view()
                    ),
                    "candidate": (
                        None
                        if self._configuration is None
                        else self._configuration.view()
                    ),
                    "readback": (
                        None if self._readback is None else self._readback.view()
                    ),
                },
                "last_frame": _copy(self._last_frame),
                "error": _copy(self._error),
                "physical_authority": False,
                "hardware_qualified": False,
            }

    def retained_diagnostics(self) -> dict[str, Any]:
        with self._state_lock:
            return self._diagnostic_copy()

    def _diagnostic_copy(self) -> dict[str, Any]:
        # Two v2 evidence pairs plus the unchanged settings/ingest allowance.
        # Legacy workflows keep their historical 1 MiB diagnostic ceiling.
        maximum = (
            1024 * 1024
            + (2 * MAX_CAMERA_ACTIVATION_CAMPAIGN_BYTES if self._activation else 0)
            + (
                MAX_CHECKSUM_BYTES + 1024
                if "capture_checksum" in self._diagnostics
                else 0
            )
        )
        return _copy(self._diagnostics, maximum=maximum)

    def _restore_campaign(self, plan):
        cls = (
            PhysicalCameraActivationCampaign
            if self._activation
            else PhysicalNativeCameraCampaign
        )
        return cls.from_plan(plan)

    def last_preview(self) -> DerivedCameraPreview | None:
        with self._state_lock:
            return (
                None
                if self._preview is None
                else replace(self._preview, transform=replace(self._preview.transform))
            )


def _copy_from_bytes(payload: bytes) -> dict[str, Any]:
    return decode_owned_json(payload, maximum=96 * 1024)
