"""Exact scoped camera-domain join; native dispatch remains independently held.

Planning/restoration is filesystem-inert. Explicit execution reads current
workspace source, but creates no directories and never substitutes a fixture
runner. A consumed M1 permit cannot qualify the dormant native runtime. Future
directory ownership and bounded capture-byte ingestion are separate unfinished
requirements, not implied by native metadata or a successful process exit.
"""

from __future__ import annotations

from dataclasses import asdict, fields
from pathlib import Path
import re
import threading
import time
from typing import Any, Callable

from .cell_commissioning_coordinator import (
    CampaignBudget,
    CampaignEvidence,
    CampaignRegistration,
    CommissioningMode,
    ExactOperationPermit,
    ObservedPowerState,
    PHYSICAL_CAMERA_COMPOSITION,
    RetainedCampaignExecution,
    WorkerReceipt,
)
from .commissioning_camera_persistence import physical_camera_source_binding
from .consumed_commissioning_scope import ConsumedCommissioningScope
from .native_camera_bounded_effect import assess_native_camera_bounded_effect
from .physical_camera_selection import PhysicalCameraSelection
from .physical_onboarding import PhysicalOnboardingStage
from .physical_onboarding_leases import LeaseLevel
from .wizard_diagnostic_coordinator import source_fingerprint
from rocell.providers.windows.camera_worker_client import (
    CameraCampaignBudget,
    CameraControlSetting,
    NativeCameraMode,
    WindowsCameraWorkerClient,
)
from rocell.providers.windows.native_camera_capture_protocol import local_capture_path
from rocell.providers.windows.native_camera_capture_registration import (
    NativeCameraCaptureRuntimeRegistration,
    PreparedOwnedNativeCapture,
    prepare_owned_native_capture,
)
from rocell.providers.windows.native_camera_protocol import (
    canonical,
    digest,
    FRAME_BYTES,
)
from rocell.providers.windows.native_camera_registration import (
    NativeCameraRuntimeRegistration,
    PreparedOwnedNativeProbe,
    prepare_owned_native_probe,
)
from rocell.providers.windows.owned_native_camera_evidence import (
    MAX_EVIDENCE_BYTES,
    OwnedNativeCameraRunEvidence,
    verify_owned_native_camera_run_evidence,
)
from rocell.providers.windows.owned_native_camera_runner import OwnedNativeCameraRunner
from rocell.providers.windows.owned_worker_process import (
    decode_owned_json,
    owned_registration_document,
)
from rocell.safety.effects import EffectClass

PLAN_SCHEMA = "rocell.physical_native_camera_campaign_plan.v1"
MAX_PLAN_BYTES = 96 * 1024
PROBE_ACTION_ID = "physical-native-camera-probe"
CAPTURE_ACTION_ID = "physical-native-camera-capture"
_PLAN_ATTEMPT = "attempt-" + "1" * 32
NativeRuntime = NativeCameraRuntimeRegistration | NativeCameraCaptureRuntimeRegistration
NativePreparation = PreparedOwnedNativeProbe | PreparedOwnedNativeCapture


class PhysicalNativeCameraCampaignError(ValueError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise PhysicalNativeCameraCampaignError(code)


def _exact_copy(value: Any, expected: type) -> Any:
    # Frozen dataclasses can still be forged; reject extra/subclass fields and
    # rerun the existing logical camera validators before taking an owned copy.
    _require(type(value) is expected, "EXACT_CAMERA_INPUT_TYPE_REQUIRED")
    _require(
        set(vars(value)) == {f.name for f in fields(expected)},
        "EXACT_CAMERA_INPUT_FIELDS_REQUIRED",
    )
    return expected(**asdict(value))


class PhysicalNativeCameraCampaign:
    """One scoped worker, no arbitrary runner or hardware-enabling option.

    The application owns origin authentication for selection/runtime, eight
    configuration epochs and reviewed stage prerequisites. This worker binds
    those immutable choices to one exact M1 attempt and original deadline.
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
        runtime: NativeRuntime,
        mode: NativeCameraMode | None = None,
        controls: tuple[CameraControlSetting, ...] = (),
        budget: CameraCampaignBudget | None = None,
    ) -> None:
        _require(
            isinstance(workspace, Path) and isinstance(assigned_parent, Path),
            "SERVER_OWNED_PATHS_REQUIRED",
        )
        workspace = local_capture_path(str(workspace))
        assigned_parent = local_capture_path(str(assigned_parent))
        physical_camera_source_binding(source_sha256)
        _require(
            type(cell_id) is str
            and bool(re.fullmatch(r"wizard-physical-camera-[0-9a-f]{16}", cell_id)),
            "PHYSICAL_CAMERA_CELL_REQUIRED",
        )
        _require(
            type(session_id) is str
            and bool(re.fullmatch(r"physical-camera-[0-9a-f]{32}", session_id)),
            "PHYSICAL_CAMERA_SESSION_REQUIRED",
        )
        _require(
            type(selection) is PhysicalCameraSelection,
            "EXACT_PHYSICAL_SELECTION_REQUIRED",
        )
        selection = PhysicalCameraSelection(selection.payload)
        _require(
            type(runtime)
            in (
                NativeCameraRuntimeRegistration,
                NativeCameraCaptureRuntimeRegistration,
            ),
            "EXACT_NATIVE_RUNTIME_REQUIRED",
        )
        runtime = type(runtime)(runtime.payload)
        registered = runtime.to_dict()
        _require(
            registered["source_sha256"] == source_sha256
            and registered["workspace"] == str(workspace)
            and selection.identity_document["source_sha256"] == source_sha256,
            "SOURCE_WORKSPACE_SELECTION_RUNTIME_MISMATCH",
        )
        _require(
            type(controls) is tuple and len(controls) <= 6,
            "EXACT_CAMERA_CONTROLS_REQUIRED",
        )
        controls = tuple(_exact_copy(item, CameraControlSetting) for item in controls)
        _require(
            controls == tuple(sorted(controls, key=lambda item: item.control_id)),
            "CANONICAL_CONTROL_ORDER_REQUIRED",
        )
        capture = type(runtime) is NativeCameraCaptureRuntimeRegistration
        if capture:
            _require(
                mode is not None and budget is not None,
                "EXPLICIT_CAPTURE_MODE_AND_BUDGET_REQUIRED",
            )
            mode = _exact_copy(mode, NativeCameraMode)
            budget = _exact_copy(budget, CameraCampaignBudget)
        else:
            _require(
                mode is None and not controls, "PROBE_HAS_NO_MODE_OR_SETTINGS_INTENT"
            )
            probe_budget = CameraCampaignBudget(5000, 1, FRAME_BYTES, FRAME_BYTES)
            budget = (
                probe_budget
                if budget is None
                else _exact_copy(budget, CameraCampaignBudget)
            )
            _require(budget == probe_budget, "EXACT_PROBE_BUDGET_REQUIRED")
        assert budget is not None
        self._plan = canonical(
            {
                "schema": PLAN_SCHEMA,
                "composition": self.composition,
                "operation": "capture" if capture else "probe",
                "cell_id": cell_id,
                "session_id": session_id,
                "workspace": str(workspace),
                "source_sha256": source_sha256,
                "assigned_parent_directory": str(assigned_parent),
                "selection": selection.identity_document,
                "selected_identity_sha256": selection.sha256,
                "runtime": registered,
                "mode": None if mode is None else asdict(mode),
                "controls": [asdict(item) for item in controls],
                "native_budget": asdict(budget),
                "campaign_timeout_ms": 25000 if capture else 20000,
                "maximum_evidence_bytes": MAX_EVIDENCE_BYTES,
                "output_policy": {
                    "working_directory_leaf": "native-camera-<attempt_id>",
                    "capture_directory_leaf": (
                        "capture-<attempt_id>" if capture else None
                    ),
                    "create_directories": False,
                    "overwrite": False,
                    "directory_ownership_qualified": False,
                    "frame_content_verified": False,
                },
                "canonical_stage_acceptance": False,
                "physical_authority": False,
                "hardware_qualified": False,
            }
        )
        _require(len(self._plan) <= MAX_PLAN_BYTES, "CAMPAIGN_PLAN_BYTE_LIMIT")
        self._used, self._lock = False, threading.Lock()
        self._evidence: bytes | None = None
        self._application_guard: Callable[[], None] | None = None
        # Exercise the actual inert logical/native preparation now, so invalid
        # dimensions, stride, controls or native ceilings fail before admission.
        # This placeholder never enters a permit or retained execution receipt.
        self._prepare(_PLAN_ATTEMPT, "1" * 64)

    @classmethod
    def from_plan(cls, value: dict[str, Any]) -> PhysicalNativeCameraCampaign:
        """Pure exact restoration; not proof of the plan's origin or approval."""
        raw = canonical(value)
        data = decode_owned_json(raw, maximum=MAX_PLAN_BYTES)
        try:
            runtime_type = (
                NativeCameraRuntimeRegistration
                if data["operation"] == "probe"
                else NativeCameraCaptureRuntimeRegistration
            )
            restored = cls(
                Path(data["workspace"]),
                Path(data["assigned_parent_directory"]),
                source_sha256=data["source_sha256"],
                cell_id=data["cell_id"],
                session_id=data["session_id"],
                selection=PhysicalCameraSelection(canonical(data["selection"])),
                runtime=runtime_type(canonical(data["runtime"])),
                mode=None if data["mode"] is None else NativeCameraMode(**data["mode"]),
                controls=tuple(
                    CameraControlSetting(**item) for item in data["controls"]
                ),
                budget=CameraCampaignBudget(**data["native_budget"]),
            )
        except (KeyError, TypeError) as error:
            raise PhysicalNativeCameraCampaignError(
                "EXACT_CAMPAIGN_PLAN_REQUIRED"
            ) from error
        _require(restored._plan == raw, "EXACT_CAMPAIGN_PLAN_REQUIRED")
        return restored

    def plan(self) -> dict[str, Any]:
        return decode_owned_json(self._plan, maximum=MAX_PLAN_BYTES)

    @property
    def worker_executable_sha256(self) -> str:
        return self.plan()["runtime"]["helper"]["sha256"]

    @property
    def evidence(self) -> OwnedNativeCameraRunEvidence | None:
        return (
            None
            if self._evidence is None
            else OwnedNativeCameraRunEvidence(self._evidence)
        )

    def registration(self) -> CampaignRegistration:
        data = self.plan()
        capture = data["operation"] == "capture"
        return CampaignRegistration(
            CAPTURE_ACTION_ID if capture else PROBE_ACTION_ID,
            (
                PhysicalOnboardingStage.CAMERA_FRAME_FRESHNESS
                if capture
                else PhysicalOnboardingStage.CAMERA_MODE_CONTROLS
            ),
            EffectClass.BOUNDED_CAMERA_CAMPAIGN,
            "scoped-physical-native-camera-" + data["operation"],
            self.worker_executable_sha256,
            digest(self._plan),
            (LeaseLevel.CAMERA,),
            # Output is bounded JSON evidence, not the separately budgeted raw
            # capture files. No binary artifacts are written by this held join.
            CampaignBudget(
                data["campaign_timeout_ms"],
                MAX_EVIDENCE_BYTES,
                1,
                data["native_budget"]["max_frames"] if capture else 0,
                len(data["controls"]),
                data["native_budget"]["max_frames"] if capture else 0,
                1,
            ),
        )

    def _prepare(self, attempt_id: str, permit_sha256: str) -> NativePreparation:
        data = self.plan()
        capture = data["operation"] == "capture"
        selected = PhysicalCameraSelection(canonical(data["selection"]))
        working = local_capture_path(data["assigned_parent_directory"]) / (
            "native-camera-" + attempt_id
        )
        registered = data["runtime"]
        client = WindowsCameraWorkerClient(
            Path(registered["helper"]["path"]), registered["helper"]["sha256"]
        )
        budget = CameraCampaignBudget(**data["native_budget"])
        common = {
            "source_sha256": data["source_sha256"],
            "campaign_id": attempt_id,
            "budget": budget,
        }
        kwargs = {
            "session_id": data["session_id"],
            "operation_sha256": digest(self._plan),
            "permit_sha256": permit_sha256,
            "working_directory": working,
        }
        if capture:
            logical = client.prepare_capture(
                selected.binding,
                NativeCameraMode(**data["mode"]),
                working / ("capture-" + attempt_id),
                controls=tuple(
                    CameraControlSetting(**item) for item in data["controls"]
                ),
                **common,
            )
            return prepare_owned_native_capture(
                NativeCameraCaptureRuntimeRegistration(canonical(registered)),
                logical,
                **kwargs,
            )
        logical = client.prepare_probe(selected.binding, **common)
        return prepare_owned_native_probe(
            NativeCameraRuntimeRegistration(canonical(registered)), logical, **kwargs
        )

    def preparation_for_permit(self, permit: ExactOperationPermit) -> NativePreparation:
        """Pure exact reconstruction for dispatch or retained-evidence audit."""
        data = self.plan()
        _require(type(permit) is ExactOperationPermit, "EXACT_PERMIT_REQUIRED")
        _require(
            permit.registration == self.registration()
            and permit.request.cell_id == permit.admission.cell_id == data["cell_id"]
            and permit.request.session_id
            == permit.admission.session_id
            == data["session_id"]
            and permit.request.action_id == self.registration().action_id
            and permit.request.expected_challenge_sha256
            == permit.admission.challenge_sha256
            and permit.admission.stage is self.registration().stage
            and permit.admission.mode is CommissioningMode.PHYSICAL_DIAGNOSTIC
            and permit.admission.source_binding_sha256
            == physical_camera_source_binding(data["source_sha256"])
            and permit.admission.selected_identity_sha256
            == data["selected_identity_sha256"]
            and permit.envelope is None,
            "EXACT_PHYSICAL_CAMERA_PERMIT_BINDING_REQUIRED",
        )
        return self._prepare(permit.attempt_id, permit.permit_sha256)

    def run_campaign(self, *args: Any, **kwargs: Any) -> Any:
        raise PhysicalNativeCameraCampaignError("SCOPED_RETAINED_EXECUTION_REQUIRED")

    def run_retained_campaign(self, *args: Any, **kwargs: Any) -> Any:
        raise PhysicalNativeCameraCampaignError("SCOPED_RETAINED_EXECUTION_REQUIRED")

    def _bind_application_guard(self, guard: Callable[[], None]) -> None:
        """Refusal-only application context check; never a release credential.

        The dispatch owner binds this once before handing the campaign to the
        core. M1 admission, consumed-scope checks and native release stay mandatory.
        The callable is process-local and is never serialized/imported in a plan.
        """
        with self._lock:
            _require(
                not self._used and self._application_guard is None and callable(guard),
                "APPLICATION_GUARD_ALREADY_BOUND_OR_INVALID",
            )
            self._application_guard = guard

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
            type(authorization) is ConsumedCommissioningScope,
            "EXACT_CONSUMED_SCOPE_REQUIRED",
        )
        prepared = self.preparation_for_permit(permit)
        _require(
            isinstance(cancellation, threading.Event)
            and type(deadline_ns) is int
            and permit.issued_at_ns < deadline_ns <= permit.expires_at_ns,
            "ORIGINAL_CAMPAIGN_DEADLINE_REQUIRED",
        )
        data, sealed_plan, sealed_permit = (
            self.plan(),
            self._plan,
            canonical(asdict(permit)),
        )
        expected_preparation = prepared.payload
        expected_registration = canonical(
            owned_registration_document(prepared.registration)
        )
        authorization.acknowledge(permit)
        application_guard = self._application_guard

        def current() -> None:
            _require(
                self._application_guard is application_guard,
                "APPLICATION_GUARD_CHANGED",
            )
            if application_guard is not None:
                _require(
                    application_guard() is None,
                    "APPLICATION_GUARD_MUST_NOT_GRANT_AUTHORITY",
                )
            _require(
                not cancellation.is_set() and time.monotonic_ns() < deadline_ns,
                "CAMPAIGN_CANCELLED_OR_EXPIRED",
            )
            _require(
                self._plan == sealed_plan
                and canonical(asdict(permit)) == sealed_permit,
                "CAMPAIGN_INPUTS_CHANGED",
            )
            _require(
                source_fingerprint(Path(data["workspace"])) == data["source_sha256"],
                "CURRENT_WORKSPACE_SOURCE_CHANGED",
            )
            # Source hashing is bounded but can outlast an application change.
            # Check again after it, especially on the last RELEASE boundary.
            if application_guard is not None:
                _require(
                    application_guard() is None,
                    "APPLICATION_GUARD_MUST_NOT_GRANT_AUTHORITY",
                )
            _require(
                not cancellation.is_set() and time.monotonic_ns() < deadline_ns,
                "CAMPAIGN_CANCELLED_OR_EXPIRED",
            )

        def revalidate(exact: NativePreparation) -> None:
            current()
            _require(
                type(exact) is type(prepared)
                and exact.payload == expected_preparation
                and canonical(owned_registration_document(exact.registration))
                == expected_registration
                and exact.camera_plan == prepared.camera_plan
                and exact.admission_request.to_dict()["permit_sha256"]
                == permit.permit_sha256
                and exact.admission_request.to_dict()["selected_identity_sha256"]
                == data["selected_identity_sha256"],
                "EXACT_NATIVE_PREPARATION_SCOPE_REQUIRED",
            )
            authorization.revalidate(permit)
            current()

        # The native hold precedes owner construction, so it never invokes the
        # after-pin/READY callbacks today. Perform an explicit current scope
        # check here as well; later callbacks still revalidate without redemption.
        revalidate(prepared)
        runner = OwnedNativeCameraRunner(
            prepared, revalidate_consumed_permit=revalidate
        )
        observed = runner.run(cancellation=cancellation, deadline_ns=deadline_ns)
        checked = verify_physical_native_camera_campaign_evidence(
            observed,
            campaign=self,
            expected_permit=permit,
            expected_evidence_sha256=observed.evidence_sha256,
        )
        self._evidence = checked.payload
        document = checked.to_dict()
        effect = assess_native_camera_bounded_effect(
            checked,
            expected_preparation=prepared,
            expected_evidence_sha256=checked.evidence_sha256,
            expected_deadline_ns=deadline_ns,
            maximum_elapsed_ns=permit.registration.budget.timeout_ms * 1_000_000,
        )
        # A missing native receipt means unknown counters after possible device
        # dispatch. Zero counts are defensible only for this observed pre-owner
        # hold; never replace an unreported activated-source count with zero.
        _require(
            effect.counts is not None,
            "NATIVE_COUNTERS_UNAVAILABLE_AFTER_DISPATCH",
        )
        assert effect.counts is not None
        counts = effect.counts
        artifact = CampaignEvidence(
            document["schema"],
            "physical-native-camera-" + data["operation"],
            checked.payload,
        )
        return RetainedCampaignExecution(
            WorkerReceipt(
                permit.attempt_id,
                permit.permit_sha256,
                self.worker_executable_sha256,
                permit.admission.selected_identity_sha256,
                # Accounting for a complete already-observed effect is not
                # runtime release, stage approval, power or pixel validation.
                effect.effect_certainty,
                effect.cleanup_confirmed,
                ObservedPowerState.UNKNOWN,
                counts.source_activation_attempts,
                counts.samples_received,
                counts.control_set_attempts,
                counts.frames_written,
                counts.source_shutdown_attempts,
                len(artifact.payload),
                (artifact.payload_sha256,),
                self.composition,
            ),
            (artifact,),
        )


def verify_physical_native_camera_campaign_evidence(
    evidence: OwnedNativeCameraRunEvidence | dict[str, Any],
    *,
    campaign: PhysicalNativeCameraCampaign,
    expected_permit: ExactOperationPermit,
    expected_evidence_sha256: str,
) -> OwnedNativeCameraRunEvidence:
    """Pure retained binding check, never replay, file read or renewed authority.

    The caller supplies the independently trusted plan/permit and evidence hash
    from audited M1 references; constructing matching objects is not approval.
    """
    _require(type(campaign) is PhysicalNativeCameraCampaign, "EXACT_CAMPAIGN_REQUIRED")
    restored = PhysicalNativeCameraCampaign.from_plan(campaign.plan())
    prepared = restored.preparation_for_permit(expected_permit)
    checked = verify_owned_native_camera_run_evidence(
        evidence,
        expected_preparation_sha256=prepared.preparation_sha256,
        expected_evidence_sha256=expected_evidence_sha256,
    )
    data = checked.to_dict()
    _require(
        data["preparation"] == prepared.to_dict()
        and data["fixture_preparation"] is None
        and data["provenance"] == "PHYSICAL_UNQUALIFIED"
        and data["source_sha256"] == restored.plan()["source_sha256"],
        "EXACT_NATIVE_EVIDENCE_DOMAIN_REQUIRED",
    )
    _require(
        type(data["parent_deadline_ns"]) is int
        and expected_permit.issued_at_ns
        < data["parent_deadline_ns"]
        <= expected_permit.expires_at_ns,
        "RETAINED_ORIGINAL_DEADLINE_REQUIRED",
    )
    return checked
