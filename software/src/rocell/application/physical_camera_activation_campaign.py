"""Exact camera-v2 campaign joining current admission to owned acquisition.

The original application owns metadata/stage authentication, runtime-review
provenance and capacity admission. This adapter independently enforces the
installed native software policy as well. No browser input, restored plan or
matching executable hash is permission. The public physical route remains
unfinished and still requires the core's already-consumed original scope.
"""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
import re
import threading
import time
from typing import Any, Callable

from .camera_activation_campaign_contract import (
    ACTION_IDS,
    WORKER_IDS,
    CONFIGURATION_CAPTURE_ACTION_ID,
    CONFIGURATION_CAPTURE_WORKER_ID,
    SEALED_CONFIGURATION_CAPTURE_ACTION_ID,
    SEALED_CONFIGURATION_CAPTURE_WORKER_ID,
    camera_activation_execution,
    RetainedCameraActivationExecution,
    validate_camera_activation_permit,
    validate_camera_activation_binding,
)
from .camera_activation_campaign_evidence import (
    CameraActivationArtifact,
    MAX_CAMERA_ACTIVATION_CAMPAIGN_BYTES,
    camera_activation_evidence,
    validate_camera_activation_evidence,
)
from .camera_activation_expectation import expectation_from_enrollment
from .camera_capture_checksum import build_capture_checksum, capture_metadata
from .camera_capture_checksum_reader import _collect_owned_capture_checksum
from .camera_sealed_capture_evidence import (
    MAX_SEALED_CAPTURE_BYTES,
    SealedCameraCaptureEvidence,
)
from .camera_sealed_capture_contract import (
    RetainedSealedCaptureExecution,
    sealed_capture_execution,
    validate_sealed_capture_binding,
)
from .camera_activation_runtime_policy import verify_reviewed_activation_runtime
from .cell_commissioning_coordinator import (
    CampaignBudget,
    CampaignRegistration,
    ExactOperationPermit,
    PHYSICAL_CAMERA_COMPOSITION,
)
from .commissioning_camera_persistence import physical_camera_source_binding
from .consumed_commissioning_scope import ConsumedCommissioningScope
from .physical_camera_selection import (
    PhysicalCameraSelection,
    selection_from_enrollment,
)
from .physical_native_camera_campaign import _exact_copy
from .physical_onboarding import PhysicalOnboardingStage
from .physical_onboarding_leases import LeaseLevel
from .wizard_diagnostic_coordinator import source_fingerprint
from .wizard_native_camera_enrollment import WizardNativeCameraEnrollment
from rocell.providers.windows.camera_worker_client import (
    CameraCampaignBudget,
    CameraControlSetting,
    NativeCameraMode,
    WindowsCameraWorkerClient,
)
from rocell.providers.windows.native_camera_activation_expectation import (
    CameraActivationExpectation,
)
from rocell.providers.windows.native_camera_activation_registration import (
    NativeCameraActivationRuntime,
    PreparedOwnedNativeActivation,
    prepare_owned_activation,
)
from rocell.providers.windows.native_camera_activation_supervisor import (
    ActivationProcessSupervisor,
)
from rocell.providers.windows.native_camera_capture_protocol import local_capture_path
from rocell.providers.windows.native_camera_protocol import (
    canonical,
    digest,
    FRAME_BYTES,
)
from rocell.providers.windows.owned_worker_process import (
    decode_owned_json,
    owned_registration_document,
)
from rocell.safety.effects import EffectClass

PLAN_SCHEMA = "rocell.physical_native_camera_activation_campaign.v2"
CONFIGURATION_PLAN_SCHEMA = "rocell.physical_native_camera_configuration_campaign.v1"
SEALED_CONFIGURATION_PLAN_SCHEMA = (
    "rocell.physical_native_camera_configuration_campaign.v2"
)
MAX_PLAN_BYTES = 96 * 1024
_PLAN_ATTEMPT = "attempt-" + "1" * 32


class CameraActivationCampaignError(ValueError):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise CameraActivationCampaignError(code)


class PhysicalCameraActivationCampaign:
    """Inert immutable plan, one explicit scoped execution, no injectable runner.

    Prefer ``from_enrollment`` at the original application boundary. Direct
    documents/restoration only validate a plan. The mandatory application guard
    rechecks their original context; the separate software policy is enforced
    internally at each scoped execution boundary.
    """

    composition = PHYSICAL_CAMERA_COMPOSITION

    def __init__(
        self,
        workspace: Path,
        assigned_parent: Path,
        *,
        source_sha256: str,
        cell_id: str,
        session_id: str,
        selection: PhysicalCameraSelection,
        expectation: CameraActivationExpectation,
        runtime: NativeCameraActivationRuntime,
        mode: NativeCameraMode | None = None,
        controls: tuple[CameraControlSetting, ...] = (),
        budget: CameraCampaignBudget | None = None,
        configuration_verification: bool = False,
        sealed_configuration_capture: bool = False,
    ) -> None:
        _require(
            isinstance(workspace, Path) and isinstance(assigned_parent, Path),
            "SERVER_OWNED_CAMERA_PATHS_REQUIRED",
        )
        workspace, assigned_parent = local_capture_path(
            str(workspace)
        ), local_capture_path(str(assigned_parent))
        physical_camera_source_binding(source_sha256)
        _require(
            type(cell_id) is str
            and re.fullmatch(r"wizard-physical-camera-[0-9a-f]{16}", cell_id)
            is not None,
            "EXACT_CAMERA_CELL_REQUIRED",
        )
        _require(
            type(session_id) is str
            and re.fullmatch(r"physical-camera-[0-9a-f]{32}", session_id) is not None,
            "EXACT_CAMERA_SESSION_REQUIRED",
        )
        _require(
            type(selection) is PhysicalCameraSelection
            and type(expectation) is CameraActivationExpectation
            and type(runtime) is NativeCameraActivationRuntime,
            "EXACT_V2_CAMERA_PLAN_INPUTS",
        )
        selection = PhysicalCameraSelection(selection.payload)
        expectation = CameraActivationExpectation(expectation.payload)
        runtime = NativeCameraActivationRuntime(runtime.payload)
        identity, expected, registered = (
            selection.identity_document,
            expectation.to_dict(),
            runtime.to_dict(),
        )
        _require(
            registered["workspace"] == str(workspace)
            and registered["source_sha256"]
            == identity["source_sha256"]
            == source_sha256,
            "CAMERA_SOURCE_WORKSPACE_RUNTIME_SELECTION_MISMATCH",
        )
        _require(
            expected["endpoint"] == identity["symbolic_link"]
            and expected["original_identity_sha256"]
            == identity["native_identity_sha256"]
            and expected["instance_id"]
            == identity["metadata_review"]["observed_instance_id"]
            and expected["container_id"]
            == identity["metadata_review"]["observed_container_id"],
            "CAMERA_ACTIVATION_EXPECTATION_SELECTION_MISMATCH",
        )
        purpose = registered["purpose"]
        _require(
            type(configuration_verification) is bool
            and (not configuration_verification or purpose == "capture"),
            "EXACT_CONFIGURATION_CAPTURE_PROFILE_REQUIRED",
        )
        _require(
            type(sealed_configuration_capture) is bool
            and (not sealed_configuration_capture or configuration_verification),
            "EXACT_SEALED_CONFIGURATION_PROFILE_REQUIRED",
        )
        _require(
            type(controls) is tuple and len(controls) <= 6,
            "EXACT_CAMERA_CONTROLS_REQUIRED",
        )
        controls = tuple(_exact_copy(item, CameraControlSetting) for item in controls)
        _require(
            controls == tuple(sorted(controls, key=lambda item: item.control_id)),
            "CANONICAL_CAMERA_CONTROL_ORDER_REQUIRED",
        )
        if purpose == "capture":
            _require(
                mode is not None and budget is not None,
                "EXPLICIT_CAPTURE_MODE_AND_BUDGET_REQUIRED",
            )
            mode, budget = _exact_copy(mode, NativeCameraMode), _exact_copy(
                budget, CameraCampaignBudget
            )
        else:
            _require(mode is None and not controls, "PROBE_HAS_NO_SETTINGS_INTENT")
            exact_budget = CameraCampaignBudget(5000, 1, FRAME_BYTES, FRAME_BYTES)
            budget = (
                exact_budget
                if budget is None
                else _exact_copy(budget, CameraCampaignBudget)
            )
            _require(budget == exact_budget, "EXACT_V2_PROBE_BUDGET_REQUIRED")
        assert budget is not None
        if configuration_verification:
            _require(
                budget.duration_ms == 5000
                and budget.max_frames == 1
                and budget.max_frame_bytes == budget.max_total_bytes,
                "CONFIGURATION_CAPTURE_EXACT_NATIVE_BUDGET",
            )
        # Omitting the extra field for v2 preserves its exact historical bytes.
        # A distinct schema/stage binds the same native intent to a new operation
        # hash; restoring this document still creates no admission or guard.
        profile = (
            dict(verification_stage=PhysicalOnboardingStage.CAMERA_MODE_CONTROLS.value)
            if configuration_verification
            else {}
        )
        self._plan = canonical(
            dict(
                schema=(
                    SEALED_CONFIGURATION_PLAN_SCHEMA
                    if sealed_configuration_capture
                    else (
                        CONFIGURATION_PLAN_SCHEMA
                        if configuration_verification
                        else PLAN_SCHEMA
                    )
                ),
                composition=self.composition,
                purpose=purpose,
                workspace=str(workspace),
                source_sha256=source_sha256,
                cell_id=cell_id,
                session_id=session_id,
                launch_session_id=identity["launch_session_id"],
                assigned_parent_directory=str(assigned_parent),
                selection=identity,
                selected_identity_sha256=selection.sha256,
                expectation=expected,
                expectation_sha256=expectation.sha256,
                runtime=registered,
                mode=None if mode is None else asdict(mode),
                controls=[asdict(item) for item in controls],
                native_budget=asdict(budget),
                campaign_timeout_ms=20_000 if purpose == "probe" else 25_000,
                maximum_evidence_bytes=(
                    MAX_SEALED_CAPTURE_BYTES
                    if sealed_configuration_capture
                    else MAX_CAMERA_ACTIVATION_CAMPAIGN_BYTES
                ),
                output_policy=dict(
                    working_directory_leaf="native-camera-<attempt_id>",
                    capture_directory_leaf=(
                        "capture-<attempt_id>" if purpose == "capture" else None
                    ),
                    creation="FRESH_IN_OWNED_PIN_LIFECYCLE",
                    reuse=False,
                    overwrite=False,
                    deletion=False,
                    frame_content_verified=False,
                ),
                original_context_authenticated=False,
                runtime_approval_inferred=False,
                physical_authority=False,
                hardware_qualified=False,
                **profile,
            )
        )
        _require(len(self._plan) <= MAX_PLAN_BYTES, "CAMERA_ACTIVATION_PLAN_BYTE_LIMIT")
        self._used, self._lock = False, threading.Lock()
        self._application_guard: Callable[[], None] | None = None
        self._evidence: (
            tuple[CameraActivationArtifact, ...] | SealedCameraCaptureEvidence | None
        ) = None
        self._post_context_failed = False
        # Validate complete intent now without issuing a real attempt or doing I/O.
        self._prepare(_PLAN_ATTEMPT, "1" * 64)

    @classmethod
    def from_enrollment(
        cls,
        workspace: Path,
        assigned_parent: Path,
        *,
        enrollment: WizardNativeCameraEnrollment,
        launch_session_id: str,
        source_sha256: str,
        cell_id: str,
        session_id: str,
        runtime: NativeCameraActivationRuntime,
        mode: NativeCameraMode | None = None,
        controls: tuple[CameraControlSetting, ...] = (),
        budget: CameraCampaignBudget | None = None,
        configuration_verification: bool = False,
        sealed_configuration_capture: bool = False,
    ) -> PhysicalCameraActivationCampaign:
        """Derive both documents through existing reviewed-metadata validators."""
        context = dict(source_sha256=source_sha256, launch_session_id=launch_session_id)
        selected = selection_from_enrollment(enrollment, **context)
        expected = expectation_from_enrollment(enrollment, **context)
        return cls(
            workspace,
            assigned_parent,
            source_sha256=source_sha256,
            cell_id=cell_id,
            session_id=session_id,
            selection=selected,
            expectation=expected,
            runtime=runtime,
            mode=mode,
            controls=controls,
            budget=budget,
            configuration_verification=configuration_verification,
            sealed_configuration_capture=sealed_configuration_capture,
        )

    @classmethod
    def from_plan(cls, value: dict[str, Any]) -> PhysicalCameraActivationCampaign:
        """Exact inert restoration, with no retained guard or executable permit."""
        raw = canonical(value)
        data = decode_owned_json(raw, maximum=MAX_PLAN_BYTES)
        try:
            restored = cls(
                Path(data["workspace"]),
                Path(data["assigned_parent_directory"]),
                source_sha256=data["source_sha256"],
                cell_id=data["cell_id"],
                session_id=data["session_id"],
                selection=PhysicalCameraSelection(canonical(data["selection"])),
                expectation=CameraActivationExpectation(canonical(data["expectation"])),
                runtime=NativeCameraActivationRuntime(canonical(data["runtime"])),
                mode=None if data["mode"] is None else NativeCameraMode(**data["mode"]),
                controls=tuple(
                    CameraControlSetting(**item) for item in data["controls"]
                ),
                budget=CameraCampaignBudget(**data["native_budget"]),
                configuration_verification=data["schema"]
                in (CONFIGURATION_PLAN_SCHEMA, SEALED_CONFIGURATION_PLAN_SCHEMA),
                sealed_configuration_capture=data["schema"]
                == SEALED_CONFIGURATION_PLAN_SCHEMA,
            )
        except (KeyError, TypeError) as error:
            raise CameraActivationCampaignError(
                "EXACT_CAMERA_ACTIVATION_PLAN_REQUIRED"
            ) from error
        _require(restored._plan == raw, "EXACT_CAMERA_ACTIVATION_PLAN_REQUIRED")
        return restored

    def plan(self) -> dict[str, Any]:
        return decode_owned_json(self._plan, maximum=MAX_PLAN_BYTES)

    @property
    def worker_executable_sha256(self) -> str:
        return self.plan()["runtime"]["helper"]["sha256"]

    @property
    def evidence(
        self,
    ) -> tuple[CameraActivationArtifact, ...] | SealedCameraCaptureEvidence | None:
        """Private full diagnostic bytes, never an ordinary public status record."""
        return self._evidence

    def status(self) -> dict[str, Any]:
        return dict(
            consumed=self._used,
            evidence_available=self._evidence is not None,
            post_context_failed=self._post_context_failed,
            physical_authority=False,
            hardware_qualified=False,
            retries=0,
        )

    def registration(self) -> CampaignRegistration:
        data = self.plan()
        purpose = data["purpose"]
        sealed = data["schema"] == SEALED_CONFIGURATION_PLAN_SCHEMA
        configuration = sealed or data["schema"] == CONFIGURATION_PLAN_SCHEMA
        frames = data["native_budget"]["max_frames"] if purpose == "capture" else 0
        return CampaignRegistration(
            (
                SEALED_CONFIGURATION_CAPTURE_ACTION_ID
                if sealed
                else (
                    CONFIGURATION_CAPTURE_ACTION_ID
                    if configuration
                    else ACTION_IDS[purpose]
                )
            ),
            (
                PhysicalOnboardingStage.CAMERA_MODE_CONTROLS
                if purpose == "probe" or configuration
                else PhysicalOnboardingStage.CAMERA_FRAME_FRESHNESS
            ),
            EffectClass.BOUNDED_CAMERA_CAMPAIGN,
            (
                SEALED_CONFIGURATION_CAPTURE_WORKER_ID
                if sealed
                else (
                    CONFIGURATION_CAPTURE_WORKER_ID
                    if configuration
                    else WORKER_IDS[purpose]
                )
            ),
            self.worker_executable_sha256,
            digest(self._plan),
            (LeaseLevel.CAMERA,),
            CampaignBudget(
                data["campaign_timeout_ms"],
                data["maximum_evidence_bytes"],
                1,
                frames,
                len(data["controls"]),
                frames,
                1,
            ),
        )

    def _prepare(
        self, attempt_id: str, permit_sha256: str
    ) -> PreparedOwnedNativeActivation:
        data = self.plan()
        runtime = NativeCameraActivationRuntime(canonical(data["runtime"]))
        selected = PhysicalCameraSelection(canonical(data["selection"]))
        working = local_capture_path(data["assigned_parent_directory"]) / (
            "native-camera-" + attempt_id
        )
        client = WindowsCameraWorkerClient(
            Path(data["runtime"]["helper"]["path"]), self.worker_executable_sha256
        )
        common = dict(
            source_sha256=data["source_sha256"],
            campaign_id=attempt_id,
            budget=CameraCampaignBudget(**data["native_budget"]),
        )
        logical = (
            client.prepare_probe(selected.binding, **common)
            if data["purpose"] == "probe"
            else client.prepare_capture(
                selected.binding,
                NativeCameraMode(**data["mode"]),
                working / ("capture-" + attempt_id),
                controls=tuple(
                    CameraControlSetting(**item) for item in data["controls"]
                ),
                **common,
            )
        )
        return prepare_owned_activation(
            runtime,
            logical,
            CameraActivationExpectation(canonical(data["expectation"])),
            session_id=data["session_id"],
            operation_sha256=digest(self._plan),
            permit_sha256=permit_sha256,
            working_directory=working,
        )

    def preparation_for_permit(
        self, permit: ExactOperationPermit
    ) -> PreparedOwnedNativeActivation:
        validate_camera_activation_permit(permit)
        data = self.plan()
        _require(
            permit.registration == self.registration()
            and permit.request.cell_id == data["cell_id"]
            and permit.request.session_id == data["session_id"]
            and permit.admission.source_binding_sha256
            == physical_camera_source_binding(data["source_sha256"])
            and permit.admission.selected_identity_sha256
            == data["selected_identity_sha256"],
            "EXACT_CAMERA_ACTIVATION_PLAN_PERMIT_REQUIRED",
        )
        return self._prepare(permit.attempt_id, permit.permit_sha256)

    def _bind_application_guard(self, guard: Callable[[], None]) -> None:
        """Bind the original service's refusal-only current-context check once."""
        with self._lock:
            _require(
                not self._used and self._application_guard is None and callable(guard),
                "EXACT_UNUSED_APPLICATION_GUARD_REQUIRED",
            )
            self._application_guard = guard

    def run_campaign(self, *args: Any, **kwargs: Any) -> Any:
        raise CameraActivationCampaignError("SCOPED_CAMERA_ACTIVATION_REQUIRED")

    def run_retained_campaign(self, *args: Any, **kwargs: Any) -> Any:
        raise CameraActivationCampaignError("SCOPED_CAMERA_ACTIVATION_REQUIRED")

    def run_scoped_campaign(
        self,
        permit: ExactOperationPermit,
        *,
        deadline_ns: int,
        cancellation: threading.Event,
        authorization: ConsumedCommissioningScope,
    ) -> RetainedCameraActivationExecution | RetainedSealedCaptureExecution:
        with self._lock:
            _require(not self._used, "CAMERA_ACTIVATION_ALREADY_CONSUMED")
            self._used = True
        _require(
            type(authorization) is ConsumedCommissioningScope,
            "EXACT_CONSUMED_CAMERA_SCOPE_REQUIRED",
        )
        prepared = self.preparation_for_permit(permit)
        _require(
            isinstance(cancellation, threading.Event)
            and type(deadline_ns) is int
            and permit.issued_at_ns < deadline_ns <= permit.expires_at_ns,
            "ORIGINAL_CAMERA_ACTIVATION_DEADLINE_REQUIRED",
        )
        application_guard = self._application_guard
        _require(application_guard is not None, "ORIGINAL_APPLICATION_GUARD_REQUIRED")
        sealed_plan, sealed_permit = self._plan, canonical(asdict(permit))
        data = self.plan()
        original_preparation = prepared.payload
        original_registration = canonical(
            owned_registration_document(prepared.registration)
        )
        authorization.acknowledge(permit)

        def current() -> None:
            _require(
                self._application_guard is application_guard,
                "CAMERA_APPLICATION_GUARD_CHANGED",
            )
            assert application_guard is not None
            _require(application_guard() is None, "APPLICATION_GUARD_MUST_RETURN_NONE")
            _require(
                not cancellation.is_set() and time.monotonic_ns() < deadline_ns,
                "CAMERA_ACTIVATION_CANCELLED_OR_EXPIRED",
            )
            _require(
                self._plan == sealed_plan
                and canonical(asdict(permit)) == sealed_permit,
                "CAMERA_ACTIVATION_INPUTS_CHANGED",
            )
            _require(
                source_fingerprint(Path(data["workspace"])) == data["source_sha256"],
                "CURRENT_CAMERA_SOURCE_CHANGED",
            )
            # A current original-context guard cannot substitute arbitrary native
            # pins. The installed software policy is checked independently, using
            # this same consumed scope's deadline, including after owner pinning.
            verify_reviewed_activation_runtime(
                NativeCameraActivationRuntime(canonical(data["runtime"])),
                cancellation=cancellation,
                deadline_ns=deadline_ns,
            )
            _require(application_guard() is None, "APPLICATION_GUARD_MUST_RETURN_NONE")
            _require(
                self._application_guard is application_guard
                and self._plan == sealed_plan
                and canonical(asdict(permit)) == sealed_permit,
                "CAMERA_ACTIVATION_INPUTS_CHANGED_AFTER_CHECK",
            )
            _require(
                not cancellation.is_set() and time.monotonic_ns() < deadline_ns,
                "CAMERA_ACTIVATION_CANCELLED_OR_EXPIRED",
            )

        def revalidate(exact: PreparedOwnedNativeActivation) -> None:
            current()
            _require(
                type(exact) is PreparedOwnedNativeActivation
                and exact.payload == original_preparation
                and canonical(owned_registration_document(exact.registration))
                == original_registration,
                "EXACT_CAMERA_PREPARATION_SCOPE_REQUIRED",
            )
            authorization.revalidate(permit)
            current()

        # No owned directory/process action precedes this current original check.
        revalidate(prepared)
        supervisor = ActivationProcessSupervisor(
            prepared, revalidate_consumed_permit=revalidate
        )
        observed = supervisor.run(cancellation=cancellation, deadline_ns=deadline_ns)
        evidence = camera_activation_evidence(prepared, observed)
        self._evidence = evidence
        if data["schema"] == SEALED_CONFIGURATION_PLAN_SCHEMA:
            # Begin with an honest no-attestation subject so late context, clock
            # or reader failures preserve the completed native observations.
            # Do not turn the native completion timestamp into a file-read time.
            _, _, metadata = capture_metadata(evidence)
            checksum = build_capture_checksum(
                evidence,
                request_key=permit.request.request_key,
                status=(
                    "NATIVE_CAPTURE_NOT_COMPLETE"
                    if metadata is None
                    else "PIXEL_READ_NOT_ATTESTED"
                ),
                frame=None,
                read_started_ns=None,
                read_finished_ns=None,
            )
            collection = SealedCameraCaptureEvidence(evidence, checksum)
            self._evidence = collection
            try:
                # Same original consumed scope and deadline; no new helper,
                # source activation or automatic second capture is introduced.
                revalidate(prepared)
                candidate = _collect_owned_capture_checksum(
                    evidence,
                    request_key=permit.request.request_key,
                    cancellation=cancellation,
                    deadline_ns=deadline_ns,
                )
                candidate_collection = SealedCameraCaptureEvidence(evidence, candidate)
                validate_sealed_capture_binding(
                    permit, candidate_collection, expected_deadline_ns=deadline_ns
                )
                collection = candidate_collection
                self._evidence = collection
                revalidate(prepared)
            except BaseException as failure:
                # The core retains returned evidence before honoring this
                # refusal, including KeyboardInterrupt. Never repair or retry.
                self._post_context_failed = True
                authorization.reject_completed_context(failure)
            return sealed_capture_execution(
                permit, collection, expected_deadline_ns=deadline_ns
            )
        execution = camera_activation_execution(
            permit, evidence, expected_deadline_ns=deadline_ns
        )
        try:
            revalidate(prepared)
        except BaseException as failure:
            # Revoke completion, but return already-observed diagnostic bytes.
            # The core sees a failed scope and retains them before quarantine.
            self._post_context_failed = True
            authorization.reject_completed_context(failure)
        return execution


def verify_camera_activation_campaign_evidence(
    evidence: tuple[CameraActivationArtifact, ...] | SealedCameraCaptureEvidence,
    *,
    campaign: PhysicalCameraActivationCampaign,
    expected_permit: ExactOperationPermit,
) -> tuple[CameraActivationArtifact, ...] | SealedCameraCaptureEvidence:
    """Pure original-plan join; the caller independently authenticates originals."""
    _require(
        type(campaign) is PhysicalCameraActivationCampaign,
        "EXACT_CAMERA_ACTIVATION_CAMPAIGN_REQUIRED",
    )
    restored = PhysicalCameraActivationCampaign.from_plan(campaign.plan())
    prepared = restored.preparation_for_permit(expected_permit)
    if restored.plan()["schema"] == SEALED_CONFIGURATION_PLAN_SCHEMA:
        validate_sealed_capture_binding(expected_permit, evidence)
        assert type(evidence) is SealedCameraCaptureEvidence
        checked = validate_camera_activation_evidence(evidence.native)
    else:
        _require(type(evidence) is tuple, "EXACT_LEGACY_CAMERA_PAIR_REQUIRED")
        assert type(evidence) is tuple
        validate_camera_activation_binding(expected_permit, evidence)
        checked = validate_camera_activation_evidence(evidence)
    _require(
        checked.prepared.payload == prepared.payload,
        "CAMERA_EVIDENCE_DIFFERS_FROM_ORIGINAL_PLAN",
    )
    return evidence
