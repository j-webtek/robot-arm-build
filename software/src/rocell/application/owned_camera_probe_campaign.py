"""One retained M1 capability probe through the fixed incapable camera child.

This uses the real native client's probe contract, not its native executable.
The explicit campaign owns one process and models one source-open/close; it
cannot produce frames, set controls, open a camera or authorize hardware.
"""

from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import sys
import threading
import time
from typing import Any, Callable

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
from .owned_camera_rehearsal_campaign import _canonical, _hash, _pin
from .physical_onboarding import PhysicalOnboardingStage
from .physical_onboarding_leases import LeaseLevel
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
    OwnedPreparedCameraRunner,
    prepare_owned_camera_fixture,
)
from rocell.providers.windows.owned_worker_process import WorkerProcessBudget
from rocell.safety.effects import EffectCertainty, EffectClass


ACTION_ID = "rehearsal-owned-camera-probe"
WORKER_ID = "incapable-owned-camera-probe"
SCHEMA = "rocell.rehearsal_camera_probe_evidence.v1"
STAGE = PhysicalOnboardingStage.CAMERA_MODE_CONTROLS
FAULTS = frozenset(
    {
        "none",
        "identity-mismatch",
        "cleanup-uncertain",
        "child-timeout",
        "malformed-result",
    }
)


class OwnedCameraProbeWorker:
    """Explicit-only, one-use probe worker with lossless pre-seal evidence."""

    composition = INCAPABLE_COMPOSITION

    def __init__(
        self,
        workspace: Path,
        directory: Path,
        *,
        source_sha256: str,
        selected_camera: dict[str, Any],
        fault: str = "none",
    ) -> None:
        if fault not in FAULTS:
            raise ValueError("Unknown owned probe scenario")
        if not directory.is_absolute() or ".." in directory.parts:
            raise ValueError("Probe requires an exact absolute session directory")
        self.workspace, self.directory = workspace, directory
        self.source_sha256, self.fault = source_sha256, fault
        self.selected_camera = json.loads(_canonical(selected_camera))
        # Only explicit execution constructs this worker. View/staging are inert.
        self._script = _pin(CAMERA_FIXTURE_PATH, 1024 * 1024)
        self.worker_executable_sha256 = self._script.sha256
        self.evidence: Any = None
        self._used = False
        self._lock = threading.Lock()
        self._plan = self.plan()

    def plan(self) -> dict[str, Any]:
        return json.loads(
            _canonical(
                {
                    "composition": INCAPABLE_COMPOSITION,
                    "process_backend": "OWNED_INCAPABLE_CAMERA_PROBE",
                    "selected_camera": self.selected_camera,
                    "fault": self.fault,
                    "native_duration_ms": 5000,
                    "process_timeout_ms": 10_000,
                    "process_cleanup_timeout_ms": 2000,
                    "stdout_bytes": 32 * 1024,
                    "stderr_bytes": 8 * 1024,
                    "frames_requested": 0,
                    "control_writes_requested": 0,
                    "artifact_qualification": "DIAGNOSTIC_ONLY_NOT_PHYSICAL_QUALIFICATION",
                }
            )
        )

    def registration(self) -> CampaignRegistration:
        return CampaignRegistration(
            ACTION_ID,
            STAGE,
            EffectClass.BOUNDED_CAMERA_CAMPAIGN,
            WORKER_ID,
            self.worker_executable_sha256,
            _hash(self._plan),
            (LeaseLevel.CAMERA,),
            CampaignBudget(60_000, MAX_RETAINED_CAMPAIGN_BYTES, 1, 0, 0, 0, 1),
        )

    def run_campaign(self, *args: Any, **kwargs: Any) -> Any:
        raise ValueError("Owned probe requires retained coordinator execution")

    def run_retained_campaign(
        self,
        permit: ExactOperationPermit,
        *,
        deadline_ns: int,
        cancellation: threading.Event,
        authorize_consumed_permit: Callable[[ExactOperationPermit], None],
    ) -> RetainedCampaignExecution:
        from .rehearsal_camera_probe_evidence import (
            retain_rehearsal_camera_probe_evidence,
        )

        with self._lock:
            if self._used:
                raise ValueError("Probe is one-use; no automatic retry")
            self._used = True
        if (
            type(permit) is not ExactOperationPermit
            or permit.registration != self.registration()
            or permit.admission.mode is not CommissioningMode.REHEARSAL
            or permit.admission.source_binding_sha256
            != rehearsal_source_binding(self.source_sha256)
            or permit.admission.selected_identity_sha256 != _hash(self.selected_camera)
            or self.plan() != self._plan
        ):
            raise ValueError("Probe permit/source/identity/plan differs")
        sealed_permit = _canonical(asdict(permit))
        # Acknowledge the coordinator's already-consumed permit once. Later
        # boundaries validate this same acknowledgment, never redeem it again.
        authorize_consumed_permit(permit)

        def check() -> None:
            if cancellation.is_set() or time.monotonic_ns() >= deadline_ns:
                raise RuntimeError("Probe cancelled/expired; do not replay")
            if _canonical(asdict(permit)) != sealed_permit or self.plan() != self._plan:
                raise ValueError("Probe inputs changed after acknowledgment")

        binding = {
            "session_id": permit.request.session_id,
            "attempt_id": permit.attempt_id,
            "source_sha256": self.source_sha256,
            "permit_sha256": permit.permit_sha256,
            "operation_sha256": permit.registration.operation_sha256,
            "selected_identity_sha256": permit.admission.selected_identity_sha256,
        }
        request = native = runner = owned_payload = None
        error = None
        try:
            check()
            require_regular_path(self.directory, directory=True)
            # The fixed child requires an empty cwd. Do not reuse the populated
            # M1 store or accept an operator-supplied path. This one attempt's
            # empty workspace is created only after consumed-permit admission.
            working_directory = self.directory / ("camera-probe-" + permit.attempt_id)
            with _directory_guard(self.directory):
                check()
                working_directory.mkdir(exist_ok=False)
            endpoint = self.selected_camera["endpoint"]
            identity = CameraEndpointBinding(
                endpoint,
                hashlib.sha256(endpoint.encode("utf-8")).hexdigest(),
                permit.admission.selected_identity_sha256,
            )
            # Native probe budgets share the typed capture structure, but no
            # frame/output request exists and the M1 frame/write ceilings are 0.
            budget = CameraCampaignBudget(5000, 1, FRAME_BYTES, FRAME_BYTES)
            client = WindowsCameraWorkerClient(CAMERA_FIXTURE_PATH, self._script.sha256)
            plan = client.prepare_probe(
                identity,
                source_sha256=self.source_sha256,
                campaign_id=permit.attempt_id,
                budget=budget,
            )
            request = plan.request
            prepared = prepare_owned_camera_fixture(
                plan,
                session_id=permit.request.session_id,
                operation_sha256=permit.registration.operation_sha256,
                selected_identity_sha256=permit.admission.selected_identity_sha256,
                expires_at_ns=deadline_ns,
                templates=(),
                executable=_pin(
                    Path(getattr(sys, "_base_executable", sys.executable)),
                    64 * 1024 * 1024,
                ),
                fixture_script=self._script,
                scenario="nominal" if self.fault == "none" else self.fault,
                working_directory=working_directory,
                budget=WorkerProcessBudget(
                    run_timeout_ms=10_000,
                    cleanup_timeout_ms=2000,
                    stdout_bytes=32 * 1024,
                    stderr_bytes=8 * 1024,
                ),
            )
            expected_reg, expected_request = prepared.registration, prepared.request
            owned_payload = json.loads(prepared.request.payload_json)
            expected_digest = prepared.request_sha256(deadline_ns)
            acknowledged = False

            def authorize_camera(request: CameraActivationRequest) -> None:
                nonlocal acknowledged
                check()
                if acknowledged or asdict(request) != asdict(plan.request):
                    raise ValueError("Probe authorization differs from exact request")
                acknowledged = True

            def authorize_owned(reg: Any, exact: Any, digest: str) -> None:
                check()
                if (
                    not acknowledged
                    or reg != expected_reg
                    or exact != expected_request
                    or digest != expected_digest
                    or source_fingerprint(self.workspace) != self.source_sha256
                ):
                    raise ValueError("Owned probe admission changed after pinning")

            runner = OwnedPreparedCameraRunner(
                prepared,
                cancellation=cancellation,
                deadline_ns=deadline_ns,
                authorize_owned=authorize_owned,
            )
            client = WindowsCameraWorkerClient(
                CAMERA_FIXTURE_PATH, self._script.sha256, runner=runner
            )
            native = client.probe(
                identity,
                source_sha256=self.source_sha256,
                campaign_id=permit.attempt_id,
                budget=budget,
                authorize=authorize_camera,
            )
            check()
        except Exception as exc:
            error = {
                "code": str(getattr(exc, "code", "OWNED_CAMERA_PROBE_FAILED")),
                "message": str(exc)[:1000],
                "error_type": type(exc).__name__,
            }
        self.evidence = retain_rehearsal_camera_probe_evidence(
            binding=binding,
            activation_request=request,
            process_result=None if runner is None else runner.owned_result,
            native_receipt=native,
            error=error,
            owned_payload=owned_payload,
        )
        artifact = CampaignEvidence(SCHEMA, "owned-camera-probe", self.evidence.payload)
        complete = self.evidence.view()["status"] == "COMPLETE_PROBE_REHEARSAL"
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
            0,
            0,
            0,
            int(bool(native and native.cleanup_confirmed)),
            len(artifact.payload),
            (artifact.payload_sha256,),
        )
        return RetainedCampaignExecution(receipt, (artifact,))
