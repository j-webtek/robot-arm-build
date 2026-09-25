"""Scoped M1 bridge for the fixed camera-incapable admission test child.

This is a stage-1 NO_DEVICE_IO orchestration diagnostic, not camera-stage
evidence or canonical stage acceptance. It cannot dispatch the real helper,
approve a native registration, enumerate metadata or issue another permit.
"""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
import threading
import time
from typing import Any

from .cell_commissioning_coordinator import (
    CampaignBudget,
    CampaignEvidence,
    CampaignRegistration,
    CommissioningMode,
    ExactOperationPermit,
    INCAPABLE_COMPOSITION,
    ObservedPowerState,
    RetainedCampaignExecution,
    WorkerReceipt,
)
from .commissioning_m1_persistence import rehearsal_source_binding
from .consumed_commissioning_scope import ConsumedCommissioningScope
from .physical_onboarding import PhysicalOnboardingStage
from .wizard_diagnostic_coordinator import require_regular_path, source_fingerprint
from .wizard_diagnostic_export import _directory_guard
from rocell.providers.windows.camera_worker_client import (
    CameraCampaignBudget,
    CameraEndpointBinding,
    WindowsCameraWorkerClient,
)
from rocell.providers.windows.native_camera_protocol import (
    canonical,
    digest,
    FRAME_BYTES,
)
from rocell.providers.windows.native_camera_registration import (
    HELPER_RELATIVE_PATH,
    PreparedOwnedNativeProbe,
    create_native_camera_runtime_registration,
    prepare_owned_native_probe,
)
from rocell.providers.windows.owned_native_camera_runner import (
    IncapableNativeAdmissionRunner,
    prepare_incapable_native_admission,
)
from rocell.providers.windows.owned_native_camera_evidence import (
    OwnedNativeCameraRunEvidence,
    SCHEMA as OWNED_EVIDENCE_SCHEMA,
)
from rocell.providers.windows.owned_worker_process import owned_registration_document
from rocell.safety.effects import EffectCertainty, EffectClass

ACTION_ID = "incapable-native-admission-diagnostic"
WORKER_ID = "fixed-incapable-native-admission"
STAGE = PhysicalOnboardingStage.WORKSPACE_SOURCES
FIXED_CHILD_SHA256 = "2dedfd13dcd57968cb06d859b7cf90017ca399a1ea774af15536efd3d0a5c4a0"
# These are logical dormant native-build pins, never dispatched or auto-approved.
_NATIVE_SHA256 = "e6072f26efa335ada46ef1459a66830a687b2d66c7ff45584aa4ac949eb027a1"
_BUILD_RECORD_SHA256 = (
    "705228b1595e1efeb2b8ceef171e3f6fdffad505b6e680b847cec352d712d7b6"
)


def incapable_native_admission_identity() -> dict[str, str]:
    """Closed fake endpoint context, never received-unit identity evidence."""
    return {
        "schema": "rocell.incapable_native_admission_identity.v1",
        "provenance": "INCAPABLE_FIXTURE",
        "endpoint": "incapable-native-admission-only",
    }


def _require(ok: bool, code: str) -> None:
    if not ok:
        raise ValueError(code)


class IncapableNativeAdmissionCampaign:
    composition = INCAPABLE_COMPOSITION
    worker_executable_sha256 = FIXED_CHILD_SHA256

    def __init__(
        self,
        workspace: Path,
        directory: Path,
        *,
        source_sha256: str,
        selected_camera: dict[str, str],
    ) -> None:
        _require(
            isinstance(workspace, Path)
            and isinstance(directory, Path)
            and workspace.is_absolute()
            and directory.is_absolute()
            and ".." not in workspace.parts
            and ".." not in directory.parts,
            "EXACT_SERVER_OWNED_DIRECTORIES_REQUIRED",
        )
        rehearsal_source_binding(source_sha256)
        _require(
            type(selected_camera) is dict
            and selected_camera == incapable_native_admission_identity(),
            "FIXED_INCAPABLE_IDENTITY_REQUIRED",
        )
        self.workspace, self.directory, self.source_sha256 = (
            workspace,
            directory,
            source_sha256,
        )
        self._identity = canonical(selected_camera)
        self._used, self._lock = False, threading.Lock()
        self.evidence: OwnedNativeCameraRunEvidence | None = None
        self._plan = canonical(self.plan())

    def plan(self) -> dict[str, Any]:
        import json

        return {
            "schema": "rocell.incapable_native_admission_campaign_plan.v1",
            "composition": INCAPABLE_COMPOSITION,
            "effect_class": EffectClass.NO_DEVICE_IO.value,
            "stage": STAGE.value,
            "canonical_stage_acceptance": False,
            "source_sha256": self.source_sha256,
            "workspace": str(self.workspace),
            "assigned_parent_directory": str(self.directory),
            "selected_camera": json.loads(self._identity),
            "worker_executable_sha256": FIXED_CHILD_SHA256,
            "native_logical_helper_sha256": _NATIVE_SHA256,
            "native_logical_build_record_sha256": _BUILD_RECORD_SHA256,
            "native_duration_ms": 5000,
            "admission_timeout_ms": 2000,
            "process_timeout_ms": 10000,
            "process_cleanup_timeout_ms": 2000,
            "campaign_timeout_ms": 20000,
            "maximum_evidence_bytes": 128 * 1024,
            "stdout_bytes": 32768,
            "stderr_bytes": 8192,
            "physical_authority": False,
            "device_effects": 0,
        }

    def registration(self) -> CampaignRegistration:
        return CampaignRegistration(
            ACTION_ID,
            STAGE,
            EffectClass.NO_DEVICE_IO,
            WORKER_ID,
            self.worker_executable_sha256,
            digest(self._plan),
            (),
            CampaignBudget(20000, 128 * 1024, 0, 0, 0, 0, 0),
        )

    def run_campaign(self, *args: Any, **kwargs: Any) -> Any:
        raise ValueError("SCOPED_RETAINED_EXECUTION_REQUIRED")

    def run_retained_campaign(self, *args: Any, **kwargs: Any) -> Any:
        raise ValueError("SCOPED_RETAINED_EXECUTION_REQUIRED")

    def run_scoped_campaign(
        self,
        permit: ExactOperationPermit,
        *,
        deadline_ns: int,
        cancellation: threading.Event,
        authorization: ConsumedCommissioningScope,
    ) -> RetainedCampaignExecution:
        with self._lock:
            _require(not self._used, "CAMPAIGN_ALREADY_CONSUMED")
            self._used = True
        _require(
            type(permit) is ExactOperationPermit
            and type(authorization) is ConsumedCommissioningScope,
            "EXACT_SCOPED_AUTHORITY_REQUIRED",
        )
        _require(
            permit.registration == self.registration()
            and permit.admission.mode is CommissioningMode.REHEARSAL
            and permit.admission.source_binding_sha256
            == rehearsal_source_binding(self.source_sha256)
            and permit.admission.selected_identity_sha256 == digest(self._identity)
            and permit.envelope is None
            and canonical(self.plan()) == self._plan,
            "SCOPED_CAMPAIGN_BINDING_MISMATCH",
        )
        _require(
            isinstance(cancellation, threading.Event)
            and type(deadline_ns) is int
            and permit.issued_at_ns < deadline_ns <= permit.expires_at_ns,
            "ORIGINAL_CAMPAIGN_LIFETIME_REQUIRED",
        )
        sealed_permit = canonical(asdict(permit))
        authorization.acknowledge(permit)

        def current() -> None:
            _require(
                not cancellation.is_set() and time.monotonic_ns() < deadline_ns,
                "SCOPED_CAMPAIGN_CANCELLED_OR_EXPIRED",
            )
            _require(
                canonical(asdict(permit)) == sealed_permit
                and canonical(self.plan()) == self._plan
                and permit.registration == self.registration(),
                "SCOPED_INPUTS_CHANGED",
            )
            _require(
                source_fingerprint(self.workspace) == self.source_sha256,
                "CURRENT_WORKSPACE_SOURCE_CHANGED",
            )

        current()
        require_regular_path(self.directory, directory=True)
        working = self.directory / ("native-admission-only-" + permit.attempt_id)
        with _directory_guard(self.directory):
            current()
            working.mkdir(exist_ok=False)
        identity = incapable_native_admission_identity()
        binding = CameraEndpointBinding(
            identity["endpoint"],
            digest(identity["endpoint"].encode()),
            digest(self._identity),
        )
        runtime = create_native_camera_runtime_registration(
            self.workspace,
            source_sha256=self.source_sha256,
            catalog_sha256=digest(self._plan),
            helper_sha256=_NATIVE_SHA256,
            build_record_sha256=_BUILD_RECORD_SHA256,
        )
        logical = WindowsCameraWorkerClient(
            self.workspace / HELPER_RELATIVE_PATH, _NATIVE_SHA256
        ).prepare_probe(
            binding,
            source_sha256=self.source_sha256,
            campaign_id=permit.attempt_id,
            budget=CameraCampaignBudget(5000, 1, FRAME_BYTES, FRAME_BYTES),
        )
        prepared = prepare_owned_native_probe(
            runtime,
            logical,
            session_id=permit.request.session_id,
            operation_sha256=permit.registration.operation_sha256,
            permit_sha256=permit.permit_sha256,
            working_directory=working,
        )
        fixture = prepare_incapable_native_admission(prepared)
        expected_prepared = prepared.payload
        expected_registered = canonical(
            owned_registration_document(fixture.registration)
        )
        _require(
            fixture.registration.executable.sha256 == self.worker_executable_sha256,
            "FIXED_INCAPABLE_EXECUTABLE_MISMATCH",
        )

        def revalidate(exact: PreparedOwnedNativeProbe) -> None:
            current()
            _require(
                type(exact) is PreparedOwnedNativeProbe
                and exact.payload == expected_prepared
                and exact.camera_plan.request == logical.request
                and exact.registration.working_directory == working
                and exact.registration.budget == prepared.registration.budget
                and canonical(owned_registration_document(fixture.registration))
                == expected_registered
                and exact.admission_request.to_dict()["selected_identity_sha256"]
                == permit.admission.selected_identity_sha256
                and exact.admission_request.to_dict()["permit_sha256"]
                == permit.permit_sha256,
                "EXACT_RUNNER_SCOPE_MISMATCH",
            )
            # Read-only after one acknowledgement: no second redemption, lease
            # renewal, TTL extension or cached verification substitute.
            authorization.revalidate(permit)
            current()

        runner = IncapableNativeAdmissionRunner(
            fixture, revalidate_consumed_permit=revalidate
        )
        self.evidence = runner.run(cancellation=cancellation, deadline_ns=deadline_ns)
        artifact = CampaignEvidence(
            OWNED_EVIDENCE_SCHEMA, "incapable-native-admission", self.evidence.payload
        )
        summary = self.evidence.safe_summary()
        complete = (
            summary["status"] == "SUCCEEDED_ADMISSION_ONLY"
            and summary["process_cleanup_confirmed"] is True
        )
        receipt = WorkerReceipt(
            permit.attempt_id,
            permit.permit_sha256,
            self.worker_executable_sha256,
            permit.admission.selected_identity_sha256,
            EffectCertainty.CONFIRMED if complete else EffectCertainty.UNCERTAIN,
            summary["process_cleanup_confirmed"],
            ObservedPowerState.UNKNOWN,
            0,
            0,
            0,
            0,
            0,
            len(artifact.payload),
            (artifact.payload_sha256,),
            INCAPABLE_COMPOSITION,
        )
        return RetainedCampaignExecution(receipt, (artifact,))
