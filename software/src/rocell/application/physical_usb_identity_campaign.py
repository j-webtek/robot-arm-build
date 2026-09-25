"""One policy-bound USB query, from original M1 admission to retained evidence.

The operation subject precedes reviews so its hash has no circular dependency
on an eventual permit. Construction is inert. Execution has no runner injection,
automatic retry, camera capture or serial path; only the owned USB helper is
reachable. Original review authentication belongs to the application service.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import re
from threading import Event, RLock
from typing import TYPE_CHECKING, Any, Callable

from .cell_commissioning_coordinator import (
    CampaignBudget,
    CampaignEvidence,
    CampaignRegistration,
    CommissioningMode,
    ExactOperationPermit,
    ObservedPowerState,
    RetainedCampaignExecution,
    WorkerReceipt,
)
from .commissioning_camera_persistence import physical_camera_source_binding
from .consumed_commissioning_scope import ConsumedCommissioningScope
from .physical_camera_selection import PhysicalCameraSelection
from .physical_onboarding import PhysicalOnboardingStage
from .physical_onboarding_leases import LeaseLevel
from .usb_identity_stage_policy import (
    UsbIdentityAdmissionIdentity,
    UsbIdentityStagePolicy,
    POLICY_ACTION,
    POLICY_COMPOSITION,
    usb_identity_stage_policy,
)
from rocell.providers.windows.owned_worker_process import decode_owned_json
from rocell.providers.windows.usb_identity_protocol import (
    UsbIdentityAdmissionRequest,
    REQUEST_SCHEMA,
    canonical,
    digest,
)
from rocell.providers.windows.usb_identity_registration import (
    UsbIdentityRuntimeRegistration,
    UsbIdentityRuntimeReview,
    PreparedOwnedUsbIdentity,
    prepare_owned_usb_identity,
)
from rocell.safety.effects import EffectCertainty, EffectClass

if TYPE_CHECKING:
    from .physical_camera_usb_qualification import UsbQualificationPlan

OPERATION_SCHEMA = "rocell.physical_usb_identity_operation.v1"
PHASE_OPERATION_SCHEMA = "rocell.physical_usb_identity_operation.v2"
MAX_OPERATION_BYTES = 80 * 1024
WORKER_ID = "scoped-physical-native-usb-identity"
_OBSERVED_PHASE_ORDINALS = {"BASELINE": 0, "AFTER_RECONNECT": 2, "AFTER_REBOOT": 3}
_OPERATION_FIELDS = {
    "schema",
    "cell_id",
    "session_id",
    "source_sha256",
    "workspace",
    "policy_sha256",
    "selection",
    "runtime",
    "physical_authority",
}


class PhysicalUsbIdentityCampaignError(ValueError):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


def _require(ok: bool, code: str) -> None:
    if not ok:
        raise PhysicalUsbIdentityCampaignError(code)


@dataclass(frozen=True, slots=True)
class UsbIdentityOperation:
    """Exact pre-review subject; no filesystem reads or hardware truth claims."""

    payload: bytes

    def __post_init__(self) -> None:
        d = decode_owned_json(self.payload, maximum=MAX_OPERATION_BYTES)
        if d.get("schema") == PHASE_OPERATION_SCHEMA:
            _require(
                canonical(d) == self.payload
                and set(d)
                == _OPERATION_FIELDS | {"qualification_plan", "phase_binding"},
                "EXACT_USB_PHASE_OPERATION_REQUIRED",
            )
            # V2 adds a subject, not a more permissive selection/runtime path.
            # Reuse the unchanged V1 validator, but never relabel retained V1
            # bytes as a new-trial observation.
            legacy = {key: d[key] for key in _OPERATION_FIELDS}
            legacy["schema"] = OPERATION_SCHEMA
            UsbIdentityOperation(canonical(legacy))
            _validate_phase_operation(d)
            return
        _require(
            canonical(d) == self.payload
            and set(d)
            == {
                "schema",
                "cell_id",
                "session_id",
                "source_sha256",
                "workspace",
                "policy_sha256",
                "selection",
                "runtime",
                "physical_authority",
            },
            "EXACT_USB_OPERATION_REQUIRED",
        )
        _require(
            d["schema"] == OPERATION_SCHEMA and d["physical_authority"] is False,
            "EXACT_USB_OPERATION_REQUIRED",
        )
        selected = PhysicalCameraSelection(canonical(d["selection"]))
        runtime = UsbIdentityRuntimeRegistration(canonical(d["runtime"]))
        _require(
            d["source_sha256"]
            == selected.identity_document["source_sha256"]
            == runtime.to_dict()["source_sha256"]
            and d["workspace"] == runtime.to_dict()["workspace"]
            and d["policy_sha256"] == usb_identity_stage_policy().sha256,
            "USB_OPERATION_SOURCE_POLICY_MISMATCH",
        )
        # Namespace validation is shared with the original physical camera store.
        _require(
            type(d["cell_id"]) is str
            and re.fullmatch(r"wizard-physical-camera-[0-9a-f]{16}", d["cell_id"])
            is not None
            and type(d["session_id"]) is str
            and re.fullmatch(r"physical-camera-[0-9a-f]{32}", d["session_id"])
            is not None,
            "EXACT_ORIGINAL_CAMERA_CONTEXT_REQUIRED",
        )

    @property
    def sha256(self) -> str:
        return digest(self.payload)

    def to_dict(self) -> dict[str, Any]:
        return decode_owned_json(self.payload, maximum=MAX_OPERATION_BYTES)


def _validate_phase_operation(d: dict[str, Any]) -> None:
    from .physical_camera_usb_qualification import UsbQualificationPlan

    plan = UsbQualificationPlan(canonical(d["qualification_plan"]))
    binding, phase = plan.to_dict()["binding"], d["phase_binding"]
    _require(
        type(phase) is dict
        and set(phase)
        == {
            "plan_sha256",
            "header_sha256",
            "trial_id",
            "phase",
            "ordinal",
            "operation_id",
            "predecessor_sha256",
        },
        "EXACT_USB_PHASE_BINDING_REQUIRED",
    )
    _require(
        type(phase["phase"]) is str
        and phase["phase"] in _OBSERVED_PHASE_ORDINALS
        and type(phase["ordinal"]) is int
        and phase["ordinal"] == _OBSERVED_PHASE_ORDINALS[phase["phase"]],
        "EXACT_OBSERVED_USB_PHASE_REQUIRED",
    )
    _require(
        type(phase["operation_id"]) is str
        and re.fullmatch(r"usbphase-[0-9a-f]{32}", phase["operation_id"]) is not None
        and type(phase["trial_id"]) is str
        and re.fullmatch(r"usbtrial-[0-9a-f]{32}", phase["trial_id"]) is not None,
        "EXACT_SERVER_USB_PHASE_IDENTIFIERS_REQUIRED",
    )
    predecessor = phase["predecessor_sha256"]
    _require(
        (
            predecessor is None
            if phase["ordinal"] == 0
            else (
                type(predecessor) is str
                and re.fullmatch(r"[0-9a-f]{64}", predecessor) is not None
            )
        ),
        "EXACT_USB_PHASE_PREDECESSOR_REQUIRED",
    )
    _require(
        all(
            d[key] == binding[key] for key in ("cell_id", "session_id", "source_sha256")
        )
        and d["policy_sha256"] == binding["stage_policy_sha256"]
        and phase["plan_sha256"] == plan.sha256
        and phase["header_sha256"] == binding["header_sha256"]
        and phase["trial_id"] == binding["trial_id"],
        "USB_PHASE_PLAN_CONTEXT_MISMATCH",
    )


def usb_identity_operation(
    *,
    cell_id: str,
    session_id: str,
    selection: PhysicalCameraSelection,
    runtime: UsbIdentityRuntimeRegistration,
    policy: UsbIdentityStagePolicy,
) -> UsbIdentityOperation:
    _require(
        type(selection) is PhysicalCameraSelection
        and type(runtime) is UsbIdentityRuntimeRegistration
        and type(policy) is UsbIdentityStagePolicy,
        "EXACT_USB_OPERATION_INPUTS",
    )
    r = runtime.to_dict()
    return UsbIdentityOperation(
        canonical(
            dict(
                schema=OPERATION_SCHEMA,
                cell_id=cell_id,
                session_id=session_id,
                source_sha256=r["source_sha256"],
                workspace=r["workspace"],
                policy_sha256=policy.sha256,
                selection=selection.identity_document,
                runtime=r,
                physical_authority=False,
            )
        )
    )


def usb_identity_phase_operation(
    *,
    plan: UsbQualificationPlan,
    phase: str,
    operation_id: str,
    predecessor_sha256: str | None,
    selection: PhysicalCameraSelection,
    runtime: UsbIdentityRuntimeRegistration,
    policy: UsbIdentityStagePolicy,
) -> UsbIdentityOperation:
    """Build the exact pre-review descriptor subject for one observed phase.

    The original-store owner supplies the server-generated operation ID and
    authenticates the plan and immediately preceding phase. These pure bytes
    neither authenticate references nor turn a MODELED plan into hardware
    evidence. RECONNECT_ABSENCE has its own presence operation, never this one.
    """
    from .physical_camera_usb_qualification import UsbQualificationPlan

    _require(
        type(plan) is UsbQualificationPlan, "EXACT_USB_QUALIFICATION_PLAN_REQUIRED"
    )
    plan = UsbQualificationPlan(plan.payload)
    _require(
        type(phase) is str and phase in _OBSERVED_PHASE_ORDINALS,
        "EXACT_OBSERVED_USB_PHASE_REQUIRED",
    )
    binding = plan.to_dict()["binding"]
    d = usb_identity_operation(
        cell_id=binding["cell_id"],
        session_id=binding["session_id"],
        selection=selection,
        runtime=runtime,
        policy=policy,
    ).to_dict()
    d.update(
        schema=PHASE_OPERATION_SCHEMA,
        qualification_plan=plan.to_dict(),
        phase_binding=dict(
            plan_sha256=plan.sha256,
            header_sha256=binding["header_sha256"],
            trial_id=binding["trial_id"],
            phase=phase,
            ordinal=_OBSERVED_PHASE_ORDINALS[phase],
            operation_id=operation_id,
            predecessor_sha256=predecessor_sha256,
        ),
    )
    return UsbIdentityOperation(canonical(d))


def verify_phase_operation_context(
    operation: UsbIdentityOperation,
    plan: UsbQualificationPlan,
    phase: str,
    operation_id: str,
    predecessor_sha256: str | None,
) -> UsbIdentityOperation:
    """Join a retained V2 operation to independently authenticated phase inputs.

    Comparing the full reconstruction prevents a valid but unrelated plan or
    phase operation from standing in for this original phase. Legacy V1 is
    readable by its own constructor but is not a trial measurement subject.
    """
    _require(type(operation) is UsbIdentityOperation, "EXACT_USB_OPERATION_REQUIRED")
    checked = UsbIdentityOperation(operation.payload)
    d = checked.to_dict()
    _require(
        d["schema"] == PHASE_OPERATION_SCHEMA, "PHASE_BOUND_USB_OPERATION_REQUIRED"
    )
    expected = usb_identity_phase_operation(
        plan=plan,
        phase=phase,
        operation_id=operation_id,
        predecessor_sha256=predecessor_sha256,
        selection=PhysicalCameraSelection(canonical(d["selection"])),
        runtime=UsbIdentityRuntimeRegistration(canonical(d["runtime"])),
        policy=usb_identity_stage_policy(),
    )
    _require(
        checked.payload == expected.payload, "USB_PHASE_OPERATION_CONTEXT_MISMATCH"
    )
    return checked


class PhysicalUsbIdentityCampaign:
    """Single-use, exact physical composition. Incapable tests use their own owner."""

    composition = POLICY_COMPOSITION

    def __init__(
        self,
        operation: UsbIdentityOperation,
        *,
        identity: UsbIdentityAdmissionIdentity,
        review: UsbIdentityRuntimeReview,
    ):
        _require(
            type(operation) is UsbIdentityOperation
            and type(identity) is UsbIdentityAdmissionIdentity
            and type(review) is UsbIdentityRuntimeReview,
            "EXACT_USB_CAMPAIGN_INPUTS",
        )
        self._operation = UsbIdentityOperation(operation.payload)
        self._identity = UsbIdentityAdmissionIdentity(identity.payload)
        self._review = UsbIdentityRuntimeReview(review.payload)
        self._lock = RLock()
        self._used = False
        self._guard: Callable[[], None] | None = None
        self._evidence: bytes | None = None
        op, selected = self._operation.to_dict(), self._identity.to_dict()
        selection = PhysicalCameraSelection(canonical(op["selection"]))
        runtime = UsbIdentityRuntimeRegistration(canonical(op["runtime"]))
        _require(
            all(
                op[k] == selected[k] for k in ("source_sha256", "cell_id", "session_id")
            )
            and selected["operation_sha256"] == operation.sha256
            and selected["stage_policy_sha256"] == op["policy_sha256"]
            and selected["selection_sha256"] == selection.sha256
            and selected["runtime_registration_sha256"] == runtime.sha256
            and selected["runtime_review_sha256"] == review.sha256,
            "USB_CAMPAIGN_IDENTITY_MISMATCH",
        )
        if op["schema"] == PHASE_OPERATION_SCHEMA:
            _require(
                op["phase_binding"]["header_sha256"] == selected["header_sha256"],
                "USB_PHASE_ORIGINAL_HEADER_MISMATCH",
            )
        # Reuse full request/preparation validation even before a real permit
        # exists. This placeholder is never returned or passed to a worker.
        self._prepare("attempt-" + "1" * 32, "1" * 64)

    @property
    def worker_executable_sha256(self) -> str:
        return self._operation.to_dict()["runtime"]["helper"]["sha256"]

    @property
    def operation(self) -> UsbIdentityOperation:
        return UsbIdentityOperation(self._operation.payload)

    @property
    def identity(self) -> UsbIdentityAdmissionIdentity:
        return UsbIdentityAdmissionIdentity(self._identity.payload)

    def registration(self) -> CampaignRegistration:
        return CampaignRegistration(
            POLICY_ACTION,
            PhysicalOnboardingStage.CAMERA_IDENTITY,
            EffectClass.BOUNDED_CAMERA_CAMPAIGN,
            WORKER_ID,
            self.worker_executable_sha256,
            self._operation.sha256,
            (LeaseLevel.CAMERA,),
            CampaignBudget(**usb_identity_stage_policy().to_dict()["budget"]),
        )

    def _prepare(self, attempt_id: str, permit_sha256: str) -> PreparedOwnedUsbIdentity:
        op = self._operation.to_dict()
        selection = PhysicalCameraSelection(canonical(op["selection"]))
        runtime = UsbIdentityRuntimeRegistration(canonical(op["runtime"]))
        sd = selection.identity_document
        instance = sd["metadata_review"]["observed_instance_id"]
        _require(
            type(instance) is str and bool(instance), "EXACT_NATIVE_INSTANCE_REQUIRED"
        )
        request = UsbIdentityAdmissionRequest(
            canonical(
                dict(
                    schema=REQUEST_SCHEMA,
                    attempt_id=attempt_id,
                    session_id=op["session_id"],
                    source_sha256=op["source_sha256"],
                    operation_sha256=self._operation.sha256,
                    selected_identity_sha256=self._identity.sha256,
                    native_identity_sha256=sd["native_identity_sha256"],
                    endpoint=sd["symbolic_link"],
                    endpoint_sha256=sd["endpoint_sha256"],
                    expected_device_instance_id=instance,
                    expected_device_instance_id_sha256=digest(instance.encode("utf-8")),
                    helper_sha256=self.worker_executable_sha256,
                    runtime_registration_sha256=runtime.sha256,
                    permit_sha256=permit_sha256,
                    native_duration_ms=10000,
                    admission_timeout_ms=5000,
                )
            )
        )
        return prepare_owned_usb_identity(
            runtime,
            review=self._review,
            expected_review_sha256=self._review.sha256,
            identity=self._identity,
            request=request,
        )

    def preparation_for_permit(
        self, permit: ExactOperationPermit
    ) -> PreparedOwnedUsbIdentity:
        from .cell_commissioning_coordinator import UsbIdentityAdmissionSnapshot

        op = self._operation.to_dict()
        _require(
            type(permit) is ExactOperationPermit
            and type(permit.admission) is UsbIdentityAdmissionSnapshot,
            "EXACT_USB_DOMAIN_PERMIT_REQUIRED",
        )
        assert isinstance(permit.admission, UsbIdentityAdmissionSnapshot)
        _require(
            canonical(asdict(permit.registration))
            == canonical(asdict(self.registration()))
            and permit.request.cell_id == permit.admission.cell_id == op["cell_id"]
            and permit.request.session_id
            == permit.admission.session_id
            == op["session_id"]
            and permit.request.action_id == POLICY_ACTION
            and permit.request.expected_challenge_sha256
            == permit.admission.challenge_sha256
            and permit.admission.mode is CommissioningMode.PHYSICAL_DIAGNOSTIC
            and permit.admission.stage is PhysicalOnboardingStage.CAMERA_IDENTITY
            and permit.admission.source_binding_sha256
            == physical_camera_source_binding(op["source_sha256"])
            and permit.admission.selected_identity_sha256 == self._identity.sha256
            and permit.admission.usb_query_policy_sha256 == op["policy_sha256"]
            and permit.envelope is None,
            "USB_PERMIT_BINDING_MISMATCH",
        )
        return self._prepare(permit.attempt_id, permit.permit_sha256)

    def _bind_application_guard(self, guard: Callable[[], None]) -> None:
        with self._lock:
            _require(
                not self._used and self._guard is None and callable(guard),
                "USB_APPLICATION_GUARD_REQUIRED_ONCE",
            )
            self._guard = guard

    def run_campaign(self, *args: Any, **kwargs: Any) -> Any:
        raise PhysicalUsbIdentityCampaignError("SCOPED_USB_EXECUTION_REQUIRED")

    def run_retained_campaign(self, *args: Any, **kwargs: Any) -> Any:
        raise PhysicalUsbIdentityCampaignError("SCOPED_USB_EXECUTION_REQUIRED")

    def run_scoped_campaign(
        self,
        permit: ExactOperationPermit,
        *,
        deadline_ns: int,
        cancellation: Event,
        authorization: ConsumedCommissioningScope,
    ) -> Any:
        from rocell.providers.windows.owned_usb_identity_runner import (
            OwnedUsbIdentityRunner,
        )
        from .cell_commissioning_coordinator import RetainedUncertainCampaignExecution

        with self._lock:
            _require(not self._used, "USB_CAMPAIGN_ALREADY_USED")
            self._used = True
            guard = self._guard
        _require(guard is not None, "USB_APPLICATION_GUARD_REQUIRED_ONCE")
        assert guard is not None
        prepared = self.preparation_for_permit(permit)
        # The runner, not this wrapper, acknowledges the consumed scope once.
        evidence = OwnedUsbIdentityRunner(
            prepared,
            permit=permit,
            authorization=authorization,
            application_guard=guard,
        ).run(cancellation=cancellation, deadline_ns=deadline_ns)
        verify_usb_identity_campaign_evidence(
            evidence,
            campaign=self,
            permit=permit,
            expected_evidence_sha256=evidence.sha256,
        )
        self._evidence = evidence.payload
        artifact = CampaignEvidence(
            evidence.to_dict()["schema"],
            "physical-native-usb-identity",
            evidence.payload,
        )
        effect = evidence.bounded_effect_summary()
        counts = effect["actual_counts"]
        if counts is None:
            # Unknown counts are not zero. Preserve the failed owned run and
            # quarantine with no WorkerReceipt claiming observations we lack.
            return RetainedUncertainCampaignExecution(
                (artifact,), ("USB_ACCOUNTING_UNAVAILABLE",)
            )
        # A complete, clean HELD native result can be a known diagnostic
        # failure. Knowing the effect outcome is separate from qualification.
        known = (
            effect["current_complete"]
            and effect["process_cleanup_confirmed"]
            and effect["usb_cleanup_confirmed"]
        )
        return RetainedCampaignExecution(
            WorkerReceipt(
                permit.attempt_id,
                permit.permit_sha256,
                self.worker_executable_sha256,
                self._identity.sha256,
                EffectCertainty.CONFIRMED if known else EffectCertainty.UNCERTAIN,
                bool(known),
                ObservedPowerState.UNKNOWN,
                counts["hub_open_attempts"],
                # Every remaining closed trace seam is a bounded metadata or
                # descriptor query; opens/closes are accounted separately.
                counts["api_calls"]
                - counts["hub_open_attempts"]
                - counts["close_attempts"],
                0,
                0,
                counts["close_attempts"],
                len(artifact.payload),
                (artifact.payload_sha256,),
                self.composition,
            ),
            (artifact,),
        )


def verify_usb_identity_campaign_evidence(
    evidence: Any,
    *,
    campaign: PhysicalUsbIdentityCampaign,
    permit: ExactOperationPermit,
    expected_evidence_sha256: str,
) -> Any:
    """Pure original-byte join; cannot replay, extend time or qualify hardware."""
    from rocell.providers.windows.owned_usb_identity_evidence import (
        OwnedUsbIdentityRunEvidence,
    )

    _require(
        type(campaign) is PhysicalUsbIdentityCampaign
        and type(evidence) is OwnedUsbIdentityRunEvidence,
        "EXACT_USB_CAMPAIGN_EVIDENCE_REQUIRED",
    )
    checked = OwnedUsbIdentityRunEvidence(evidence.payload)
    prepared = campaign.preparation_for_permit(permit)
    d = checked.to_dict()
    _require(
        checked.sha256 == expected_evidence_sha256
        and d["preparation_sha256"] == prepared.sha256
        and canonical(d["preparation"]) == prepared.payload,
        "USB_ORIGINAL_CAMPAIGN_EVIDENCE_MISMATCH",
    )
    # Reopening verifies the original absolute bounds, not today's clock.
    # The original armed timestamp is not in this evidence, so this verifies
    # ranges rather than pretending to reconstruct its exact deadline formula.
    _require(
        permit.issued_at_ns < d["original_deadline_ns"] <= permit.expires_at_ns
        and d["original_deadline_ns"]
        <= d["started_monotonic_ns"]
        + permit.registration.budget.timeout_ms * 1_000_000,
        "USB_ORIGINAL_DEADLINE_OUTSIDE_PERMIT",
    )
    return checked
