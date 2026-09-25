"""M1 consumed-permit camera campaign using one contained, incapable process.

Templates use the existing nominal placemat renderer. The unchanged native
camera client validates the child protocol; the existing ingestion path derives
the preview from its actual YUY2 files. No native camera/serial API is available
through this composition. Process cleanup is not physical device-close proof.
"""

from __future__ import annotations

from dataclasses import asdict
import hashlib
from io import BytesIO
import json
import os
from pathlib import Path
import shutil
import sys
import threading
import time
from typing import Any, Callable
import uuid

from .camera_capture_dataset import FramePlan, PreviewTransform
from .camera_configuration import (
    CameraCapabilities,
    StagedCameraConfiguration,
    compare_camera_readback,
    verify_camera_configuration,
)
from .wizard_camera_configuration import effective_camera_settings_epoch
from .camera_rehearsal_campaign import MODE, camera_settings
from .cell_commissioning_coordinator import (
    CampaignBudget,
    CampaignEvidence,
    CampaignRegistration,
    CommissioningMode,
    ExactOperationPermit,
    INCAPABLE_COMPOSITION,
    MAX_RETAINED_CAMPAIGN_BYTES,
    ObservedPowerState,
    RetainedCampaignExecution,
    WorkerReceipt,
)
from .commissioning_m1_persistence import rehearsal_source_binding
from .physical_onboarding import PhysicalOnboardingStage
from .physical_onboarding_leases import LeaseLevel
from .rehearsal_owned_camera_evidence import retain_owned_camera_evidence
from .windows_camera_capture_ingest import (
    prepare_windows_camera_ingest,
    ingest_windows_capture,
)
from .wizard_diagnostic_coordinator import require_regular_path, source_fingerprint
from .wizard_diagnostic_export import _directory_guard
from rocell.providers.windows.camera_worker_client import (
    CameraActivationRequest,
    CameraCampaignBudget,
    CameraEndpointBinding,
    WindowsCameraWorkerClient,
)
from rocell.providers.windows.owned_camera_runner import (
    CAMERA_FIXTURE_PATH,
    FRAME_BYTES,
    TEMPLATE_BYTES,
    OwnedPreparedCameraRunner,
    prepare_owned_camera_fixture,
)
from rocell.providers.windows.owned_worker_process import (
    PinnedWorkerFile,
    WorkerProcessBudget,
)
from rocell.safety.effects import EffectCertainty, EffectClass

ACTION_ID = "rehearsal-owned-camera-campaign"
WORKER_ID = "incapable-owned-camera-campaign"
SCHEMA = "rocell.rehearsal_owned_camera_evidence.v1"
FAULTS = frozenset(
    {
        "none",
        "identity-mismatch",
        "cleanup-uncertain",
        "child-timeout",
        "malformed-result",
        "control-readback-drift",
    }
)
_STAGES = frozenset(
    {
        PhysicalOnboardingStage.CAMERA_MODE_CONTROLS,
        PhysicalOnboardingStage.CAMERA_FRAME_FRESHNESS,
    }
)


def _canonical(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("ascii")


def _hash(value: object) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _pin(path: Path, maximum: int) -> PinnedWorkerFile:
    """Explicit bounded preflight; the owned runner locks/rechecks these pins."""
    require_regular_path(path, directory=False)
    if path.stat().st_size > maximum:
        raise ValueError("Fixed camera process file exceeds its byte budget")
    digest = hashlib.sha256()
    total = 0
    with path.open("rb") as stream:
        while block := stream.read(64 * 1024):
            total += len(block)
            if total > maximum:
                raise ValueError("Fixed camera process file grew during preflight")
            digest.update(block)
    return PinnedWorkerFile(path, digest.hexdigest(), maximum)


def _read_contract(path: Path, digest: str) -> dict[str, Any]:
    require_regular_path(path, directory=False)
    with path.open("rb") as stream:
        payload = stream.read(128 * 1024 + 1)
    if len(payload) > 128 * 1024 or hashlib.sha256(payload).hexdigest() != digest:
        raise ValueError("Retained camera contract changed or exceeds its bound")
    value = json.loads(payload)
    if type(value) is not dict:
        raise ValueError("Retained camera contract is not an object")
    return value


class OwnedBinaryCameraWorker:
    """One-use retained coordinator worker, sealed to the fixed camera fixture."""

    composition = INCAPABLE_COMPOSITION

    def __init__(
        self,
        workspace: Path,
        root: Path,
        *,
        source_sha256: str,
        frame_count: int,
        fault: str,
        settings: dict[str, Any],
        settings_epoch: str,
        selected_camera: dict[str, Any],
        configuration: StagedCameraConfiguration | None = None,
        capabilities: CameraCapabilities | None = None,
    ) -> None:
        if (
            type(frame_count) is not int
            or not 1 <= frame_count <= 4
            or fault not in FAULTS
        ):
            raise ValueError("Unknown or oversized owned camera rehearsal")
        if (
            settings != camera_settings(settings.get("brightness_offset"))
            or _hash(settings) != settings_epoch
        ):
            raise ValueError("Owned camera settings differ from their exact epoch")
        if not root.is_absolute() or ".." in root.parts:
            raise ValueError("Assign an absolute session-owned artifact root")
        self.workspace, self.root = workspace, root
        self.source_sha256, self.frame_count, self.fault = (
            source_sha256,
            frame_count,
            fault,
        )
        self.settings = json.loads(_canonical(settings))
        self.settings_epoch = settings_epoch
        self.selected_camera = json.loads(_canonical(selected_camera))
        if (configuration is None) != (capabilities is None):
            raise ValueError("Configuration and verified probe capabilities are paired")
        self.configuration = None
        if configuration is not None:
            assert capabilities is not None
            self.configuration = verify_camera_configuration(
                configuration.payload, expected_capabilities=capabilities
            )
            data = self.configuration.to_dict()
            if (
                data["source_sha256"] != source_sha256
                or data["selected_identity_sha256"] != _hash(selected_camera)
                or not self.configuration.mode.same_format(MODE)
            ):
                raise ValueError(
                    "Configuration source, identity or fixture mode differs"
                )
        if fault == "control-readback-drift" and (
            self.configuration is None or not self.configuration.controls
        ):
            raise ValueError("Readback drift requires staged electronic controls")
        self.effective_settings_epoch = (
            effective_camera_settings_epoch(settings_epoch, self.configuration)
            if self.configuration is not None
            else settings_epoch
        )
        self.readback: dict[str, Any] | None = None
        # Constructor is used only by explicit execution, never by view/preview.
        self._script = _pin(CAMERA_FIXTURE_PATH, 1024 * 1024)
        self.worker_executable_sha256 = self._script.sha256
        self.capture: Any = None
        self.evidence: Any = None
        self._used = False
        self._lock = threading.Lock()
        self._operation_plan = json.loads(_canonical(self.plan()))

    def plan(self) -> dict[str, Any]:
        plan = {
            "composition": INCAPABLE_COMPOSITION,
            "process_backend": "OWNED_INCAPABLE_CAMERA_PROCESS",
            "selected_camera": self.selected_camera,
            "mode": {
                "width": 5472,
                "height": 3648,
                "fps_numerator": 9,
                "fps_denominator": 1,
                "pixel_format": "YUY2",
            },
            "frame_count": self.frame_count,
            "fault": self.fault,
            "settings": self.settings,
            "settings_epoch": self.settings_epoch,
            "native_frame_bytes_generated": True,
            "binary_artifact_budget_bytes": (2 * FRAME_BYTES + TEMPLATE_BYTES)
            * self.frame_count
            + 128 * 1024 * 1024,
            "artifact_qualification": "DIAGNOSTIC_ONLY_NOT_M1_QUALIFIED",
            "process_timeout_ms": 25_000,
            "process_cleanup_timeout_ms": 2000,
            "native_duration_ms": 20_000,
            "stdout_bytes": 32 * 1024,
            "stderr_bytes": 8 * 1024,
        }
        if self.configuration is not None:
            plan.update(
                electronic_configuration=self.configuration.to_dict(),
                probe_evidence_sha256=self.configuration.to_dict()[
                    "probe_evidence_sha256"
                ],
                effective_settings_epoch=self.effective_settings_epoch,
            )
        return json.loads(_canonical(plan))

    def registration(self, stage: PhysicalOnboardingStage) -> CampaignRegistration:
        if stage not in _STAGES:
            raise ValueError("Owned camera campaign requires a due camera stage")
        return CampaignRegistration(
            ACTION_ID,
            stage,
            EffectClass.BOUNDED_CAMERA_CAMPAIGN,
            WORKER_ID,
            self.worker_executable_sha256,
            _hash(self._operation_plan),
            (LeaseLevel.CAMERA,),
            CampaignBudget(
                60_000,
                MAX_RETAINED_CAMPAIGN_BYTES,
                1,
                self.frame_count,
                len(self.configuration.controls) if self.configuration else 0,
                self.frame_count,
                1,
            ),
        )

    def run_campaign(self, *args: Any, **kwargs: Any) -> Any:
        raise ValueError(
            "Owned camera requires the coordinator's retained-evidence path"
        )

    def run_retained_campaign(
        self,
        permit: ExactOperationPermit,
        *,
        deadline_ns: int,
        cancellation: threading.Event,
        authorize_consumed_permit: Callable[[ExactOperationPermit], None],
    ) -> RetainedCampaignExecution:
        with self._lock:
            if self._used:
                raise ValueError("Owned camera worker is one-use; no retry")
            self._used = True
        if (
            type(permit) is not ExactOperationPermit
            or permit.registration != self.registration(permit.registration.stage)
            or permit.admission.mode is not CommissioningMode.REHEARSAL
            or permit.admission.source_binding_sha256
            != rehearsal_source_binding(self.source_sha256)
            or permit.admission.selected_identity_sha256 != _hash(self.selected_camera)
            or (
                self.configuration is not None
                and self.configuration.to_dict()["session_id"]
                != permit.request.session_id
            )
            or self.plan() != self._operation_plan
        ):
            raise ValueError("Owned camera permit/source/identity/settings differ")
        sealed_permit = _canonical(asdict(permit))
        # Acknowledge already-consumed M1 authority exactly once while the
        # coordinator holds its leases. Later callbacks check this same attempt;
        # neither callback mints or redeems a second permit.
        authorize_consumed_permit(permit)

        def check() -> None:
            if cancellation.is_set() or time.monotonic_ns() >= deadline_ns:
                raise RuntimeError("Owned camera cancelled or expired; no replay")
            if (
                _canonical(asdict(permit)) != sealed_permit
                or self.plan() != self._operation_plan
            ):
                raise ValueError("Owned camera inputs changed after acknowledgement")

        binding = {
            "session_id": permit.request.session_id,
            "attempt_id": permit.attempt_id,
            "source_sha256": self.source_sha256,
            "permit_sha256": permit.permit_sha256,
            "operation_sha256": permit.registration.operation_sha256,
            "selected_identity_sha256": permit.admission.selected_identity_sha256,
            "settings_epoch": self.effective_settings_epoch,
        }
        request = native = runner = envelope = source_contract = None
        error = None
        try:
            check()
            destination, raw, datasets, templates = self._prepare_templates(check)
            endpoint = self.selected_camera["endpoint"]
            camera_binding = CameraEndpointBinding(
                endpoint,
                hashlib.sha256(endpoint.encode()).hexdigest(),
                permit.admission.selected_identity_sha256,
            )
            budget = CameraCampaignBudget(
                20_000, self.frame_count, FRAME_BYTES, FRAME_BYTES * self.frame_count
            )
            client = WindowsCameraWorkerClient(CAMERA_FIXTURE_PATH, self._script.sha256)
            native_plan = client.prepare_capture(
                camera_binding,
                MODE,
                raw,
                source_sha256=self.source_sha256,
                campaign_id=permit.attempt_id,
                budget=budget,
                controls=self.configuration.controls if self.configuration else (),
            )
            request = native_plan.request
            prepared = prepare_owned_camera_fixture(
                native_plan,
                session_id=permit.request.session_id,
                operation_sha256=permit.registration.operation_sha256,
                selected_identity_sha256=permit.admission.selected_identity_sha256,
                expires_at_ns=deadline_ns,
                templates=templates,
                executable=_pin(
                    Path(getattr(sys, "_base_executable", sys.executable)),
                    64 * 1024 * 1024,
                ),
                fixture_script=self._script,
                scenario="nominal" if self.fault == "none" else self.fault,
                budget=WorkerProcessBudget(
                    run_timeout_ms=25_000,
                    cleanup_timeout_ms=2000,
                    stdout_bytes=32 * 1024,
                    stderr_bytes=8 * 1024,
                ),
            )
            expected_reg, expected_request = prepared.registration, prepared.request
            expected_digest = prepared.request_sha256(deadline_ns)
            camera_acknowledged = False

            def authorize_camera(request: CameraActivationRequest) -> None:
                nonlocal camera_acknowledged
                check()
                if camera_acknowledged or asdict(request) != asdict(
                    native_plan.request
                ):
                    raise ValueError(
                        "Camera authorization differs from the single exact request"
                    )
                camera_acknowledged = True

            def authorize_owned(reg: Any, exact: Any, digest: str) -> None:
                check()
                if (
                    not camera_acknowledged
                    or reg != expected_reg
                    or exact != expected_request
                    or digest != expected_digest
                    or source_fingerprint(self.workspace) != self.source_sha256
                ):
                    raise ValueError(
                        "Owned process admission differs from acknowledged camera attempt"
                    )

            runner = OwnedPreparedCameraRunner(
                prepared,
                cancellation=cancellation,
                deadline_ns=deadline_ns,
                authorize_owned=authorize_owned,
            )
            client = WindowsCameraWorkerClient(
                CAMERA_FIXTURE_PATH, self._script.sha256, runner=runner
            )
            native = client.capture(
                camera_binding,
                MODE,
                raw,
                source_sha256=self.source_sha256,
                campaign_id=permit.attempt_id,
                budget=budget,
                authorize=authorize_camera,
                controls=self.configuration.controls if self.configuration else (),
            )
            check()
            if self.configuration is not None:
                self.readback = compare_camera_readback(
                    self.configuration,
                    native,
                    expected_settings_epoch=self.configuration.settings_epoch,
                )
                if self.readback["status"] != "REQUESTED_SETTINGS_OBSERVED_REHEARSAL":
                    raise ValueError("Independent camera settings readback differs")
            if (
                runner.owned_result is None
                or runner.owned_result.status != "SUCCEEDED"
                or native.status != "OK"
                or not native.cleanup_confirmed
            ):
                raise ValueError(
                    "Contained process/native capture is incomplete; do not ingest"
                )
            remaining_ms = min(20_000, (deadline_ns - time.monotonic_ns()) // 1_000_000)
            if remaining_ms < 100:
                raise RuntimeError("No camera retention budget remains")
            ingest_plan = prepare_windows_camera_ingest(
                request,
                capture_directory=raw,
                dataset_root=datasets,
                source_sha256=self.source_sha256,
                settings_epoch=self.effective_settings_epoch,
                domain="INCAPABLE_NATIVE_FIXTURE",
                frames=tuple(
                    FramePlan(
                        f"frame-{i:06d}",
                        preview=(
                            PreviewTransform(0, 0, 5472, 3648, 912, 608)
                            if i == self.frame_count - 1
                            else None
                        ),
                    )
                    for i in range(self.frame_count)
                ),
                retention_timeout_ms=int(remaining_ms),
            )
            self.capture = ingest_windows_capture(
                request,
                native,
                plan=ingest_plan,
                cancelled=lambda: cancellation.is_set()
                or time.monotonic_ns() >= deadline_ns,
            )
            check()
            envelope = _read_contract(
                self.capture.envelope_path, self.capture.envelope_sha256
            )
            source_contract = _read_contract(
                self.capture.envelope_path.parent / "source-contract.json",
                self.capture.source_contract_sha256,
            )
        except Exception as exc:
            error = {
                "code": str(getattr(exc, "code", "OWNED_CAMERA_CAMPAIGN_FAILED")),
                "message": str(exc)[:1000],
                "error_type": type(exc).__name__,
            }
        process = None if runner is None else runner.owned_result
        self.evidence = retain_owned_camera_evidence(
            binding=binding,
            activation_request=request,
            process_result=process,
            native_receipt=native,
            capture=self.capture,
            error=error,
            capture_envelope=envelope,
            source_contract=source_contract,
        )
        artifact = CampaignEvidence(
            SCHEMA, "owned-camera-campaign", self.evidence.payload
        )
        complete = self.evidence.view()["status"] == "RETAINED_COMPLETE_REHEARSAL"
        counts = {} if native is None else native.counts
        receipt = WorkerReceipt(
            permit.attempt_id,
            permit.permit_sha256,
            self.worker_executable_sha256,
            permit.admission.selected_identity_sha256,
            EffectCertainty.CONFIRMED if complete else EffectCertainty.UNCERTAIN,
            complete,
            ObservedPowerState.UNKNOWN,
            counts.get("source_opened", 0),
            counts.get("samples_received", 0),
            counts.get("control_set_attempts", 0),
            counts.get("frames_written", 0),
            int(bool(native and native.cleanup_confirmed)),
            len(artifact.payload),
            (artifact.payload_sha256,),
        )
        return RetainedCampaignExecution(receipt, (artifact,))

    def _prepare_templates(
        self, check: Callable[[], None]
    ) -> tuple[Path, Path, Path, tuple[PinnedWorkerFile, ...]]:
        from PIL import Image
        from .b0477_static_vision import run_b0477_static_vision_capture_rehearsal

        require_regular_path(self.root, directory=True)
        destination = self.root / ("binary-fixture-" + uuid.uuid4().hex)
        raw, datasets, templates = (
            destination / "native",
            destination / "datasets",
            destination / "templates",
        )
        pins = []
        with _directory_guard(self.root):
            check()
            if (
                shutil.disk_usage(self.root).free
                < self._operation_plan["binary_artifact_budget_bytes"]
            ):
                raise RuntimeError(
                    "Insufficient disk for templates/raw/retained camera bytes"
                )
            destination.mkdir(exist_ok=False)
            for directory in (raw, datasets, templates):
                directory.mkdir(exist_ok=False)
            offset = self.settings["brightness_offset"]
            lut = bytes(
                16 + (max(0, min(255, v + offset)) * 219 + 127) // 255
                for v in range(256)
            )
            for index in range(self.frame_count):
                check()
                capture = run_b0477_static_vision_capture_rehearsal(
                    self.workspace, sequence=index
                )
                with Image.open(BytesIO(capture.jpeg_bytes)) as encoded:
                    gray = encoded.convert("L")
                try:
                    if gray.size != (2736, 1824):
                        raise ValueError(
                            "Source-derived placemat template size changed"
                        )
                    digest = hashlib.sha256()
                    path = templates / f"frame-{index:06d}.gray8"
                    with path.open("xb") as stream:
                        for row in range(1824):
                            check()
                            block = (
                                gray.crop((0, row, 2736, row + 1))
                                .tobytes()
                                .translate(lut)
                            )
                            if stream.write(block) != len(block):
                                raise OSError("Short template write")
                            digest.update(block)
                        stream.flush()
                        os.fsync(stream.fileno())
                    pins.append(
                        PinnedWorkerFile(path, digest.hexdigest(), TEMPLATE_BYTES)
                    )
                finally:
                    gray.close()
        return destination, raw, datasets, tuple(pins)
