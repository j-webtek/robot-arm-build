"""Exact camera-v2 retention domain and result accounting; no permission grant.

The coordinator and original store independently call these checks. They do not
replace the active consumed scope or accepted original campaign plan. Legacy
camera/USB evidence types, integer receipt fields and byte limits stay unchanged.
"""

from dataclasses import dataclass
import re
from types import MappingProxyType

from .camera_activation_campaign_evidence import (
    CameraActivationArtifact,
    MAX_CAMERA_ACTIVATION_CAMPAIGN_BYTES,
    validate_camera_activation_evidence,
)
from .cell_commissioning_coordinator import (
    AdmissionSnapshot,
    CampaignBudget,
    CampaignRegistration,
    CommissioningMode,
    ExactOperationPermit,
    ObservedPowerState,
    RegisteredActionRequest,
    WorkerReceipt,
    PHYSICAL_CAMERA_COMPOSITION,
)
from .physical_onboarding import PhysicalOnboardingStage
from .physical_onboarding_leases import LeaseLevel
from rocell.safety.effects import EffectClass, EffectCertainty
from rocell.providers.windows.native_camera_protocol import _require

ACTION_IDS = MappingProxyType(
    {
        "probe": "physical-native-camera-activation-probe-v2",
        "capture": "physical-native-camera-activation-capture-v2",
    }
)
WORKER_IDS = MappingProxyType(
    {purpose: "scoped-" + action for purpose, action in ACTION_IDS.items()}
)
# A settings readback must be possible before stage 5 can pass. Keep the old
# two-purpose mapping unchanged: this is a distinct application action using
# the existing native capture protocol, not a widened v2 freshness permit.
CONFIGURATION_CAPTURE_ACTION_ID = "physical-native-camera-configuration-capture-v1"
CONFIGURATION_CAPTURE_WORKER_ID = "scoped-" + CONFIGURATION_CAPTURE_ACTION_ID
# A distinct closed contract can bind the post-cleanup checksum into original
# receipt accounting. The old v1 capture and native v2 pair remain unchanged.
SEALED_CONFIGURATION_CAPTURE_ACTION_ID = (
    "physical-native-camera-configuration-capture-v2"
)
SEALED_CONFIGURATION_CAPTURE_WORKER_ID = (
    "scoped-" + SEALED_CONFIGURATION_CAPTURE_ACTION_ID
)
_STAGES = MappingProxyType(
    {
        "probe": PhysicalOnboardingStage.CAMERA_MODE_CONTROLS,
        "capture": PhysicalOnboardingStage.CAMERA_FRAME_FRESHNESS,
    }
)
_REASON = re.compile(r"[A-Z][A-Z0-9_]{0,63}\Z")


def is_camera_activation_action(permit: ExactOperationPermit) -> bool:
    """Routing predicate only. A matching name does not validate a permit."""
    return type(permit) is ExactOperationPermit and (
        permit.registration.action_id in ACTION_IDS.values()
        or permit.registration.action_id
        in (CONFIGURATION_CAPTURE_ACTION_ID, SEALED_CONFIGURATION_CAPTURE_ACTION_ID)
    )


def validate_camera_activation_permit(permit: ExactOperationPermit) -> str:
    _require(type(permit) is ExactOperationPermit, "EXACT_CAMERA_ACTIVATION_PERMIT")
    reg, request, admission = permit.registration, permit.request, permit.admission
    for value, expected in (
        (reg, CampaignRegistration),
        (request, RegisteredActionRequest),
        (admission, AdmissionSnapshot),
    ):
        _require(type(value) is expected, "EXACT_CAMERA_ACTIVATION_PERMIT_FIELDS")
        value.__post_init__()
    purposes = [
        purpose for purpose, action in ACTION_IDS.items() if reg.action_id == action
    ]
    sealed = reg.action_id == SEALED_CONFIGURATION_CAPTURE_ACTION_ID
    configuration = reg.action_id == CONFIGURATION_CAPTURE_ACTION_ID or sealed
    if configuration:
        purposes = ["capture"]
    _require(len(purposes) == 1, "CAMERA_ACTIVATION_ACTION_ID")
    purpose = purposes[0]
    stage = (
        PhysicalOnboardingStage.CAMERA_MODE_CONTROLS
        if configuration
        else _STAGES[purpose]
    )
    worker = (
        SEALED_CONFIGURATION_CAPTURE_WORKER_ID
        if sealed
        else (CONFIGURATION_CAPTURE_WORKER_ID if configuration else WORKER_IDS[purpose])
    )
    _require(
        request.action_id == reg.action_id
        and reg.worker_id == worker
        and reg.stage is stage
        and admission.stage is reg.stage
        and reg.effect_class is EffectClass.BOUNDED_CAMERA_CAMPAIGN
        and reg.resources == (LeaseLevel.CAMERA,)
        and admission.mode is CommissioningMode.PHYSICAL_DIAGNOSTIC
        and permit.envelope is None,
        "CAMERA_ACTIVATION_RETENTION_DOMAIN",
    )
    _require(
        request.cell_id == admission.cell_id
        and request.session_id == admission.session_id
        and re.fullmatch(r"wizard-physical-camera-[0-9a-f]{16}", request.cell_id)
        is not None
        and re.fullmatch(r"physical-camera-[0-9a-f]{32}", request.session_id)
        is not None
        and request.expected_challenge_sha256 == admission.challenge_sha256,
        "CAMERA_ACTIVATION_ORIGINAL_CONTEXT",
    )
    from .camera_capture_checksum import MAX_BYTES as CHECKSUM_MAX_BYTES

    evidence_limit = MAX_CAMERA_ACTIVATION_CAMPAIGN_BYTES + (
        CHECKSUM_MAX_BYTES if sealed else 0
    )
    _require(
        type(reg.budget) is CampaignBudget
        and reg.budget.timeout_ms == (20_000 if purpose == "probe" else 25_000)
        and reg.budget.maximum_output_bytes == evidence_limit
        and reg.budget.maximum_opens == reg.budget.maximum_closes == 1
        and type(permit.issued_at_ns) is int
        and type(permit.expires_at_ns) is int
        and 0 < permit.issued_at_ns < permit.expires_at_ns < 2**63,
        "CAMERA_ACTIVATION_ORIGINAL_LIMITS",
    )
    _require(
        not configuration or reg.budget.maximum_reads == reg.budget.maximum_frames == 1,
        "CONFIGURATION_CAPTURE_ONE_FRAME_REQUIRED",
    )
    return purpose


def validate_camera_activation_binding(
    permit: ExactOperationPermit,
    artifacts: tuple[CameraActivationArtifact, ...],
    *,
    expected_deadline_ns: int | None = None,
) -> None:
    """Bind full decoded request and finite intent to the original permit."""
    _require(
        type(permit) is ExactOperationPermit
        and permit.registration.action_id != SEALED_CONFIGURATION_CAPTURE_ACTION_ID,
        "LEGACY_PAIR_CANNOT_REPLACE_SEALED_CAPTURE",
    )
    _validate_camera_activation_native_binding(
        permit, artifacts, expected_deadline_ns=expected_deadline_ns
    )


def _validate_camera_activation_native_binding(
    permit, artifacts, *, expected_deadline_ns=None
):
    """Shared pure native identity/count check; not complete checksum validation."""
    # Import after coordinator initialization; this function reads no stores.
    from .commissioning_camera_persistence import physical_camera_source_binding

    purpose = validate_camera_activation_permit(permit)
    checked = validate_camera_activation_evidence(artifacts)
    prepared = checked.prepared
    request = prepared.admission_request.to_dict()
    data = checked.run.to_dict()
    _require(
        prepared.admission_request.purpose == purpose
        and request["attempt_id"] == permit.attempt_id
        and request["permit_sha256"] == permit.permit_sha256
        and request["session_id"] == permit.request.session_id
        and request["operation_sha256"] == permit.registration.operation_sha256
        and request["helper_sha256"] == permit.registration.worker_executable_sha256
        and request["selected_identity_sha256"]
        == permit.admission.selected_identity_sha256
        and physical_camera_source_binding(request["source_sha256"])
        == permit.admission.source_binding_sha256,
        "CAMERA_ACTIVATION_EVIDENCE_PERMIT_BINDING",
    )
    native = prepared.camera_plan.request
    if permit.registration.action_id in (
        CONFIGURATION_CAPTURE_ACTION_ID,
        SEALED_CONFIGURATION_CAPTURE_ACTION_ID,
    ):
        _require(
            native.budget.duration_ms == 5000
            and native.budget.max_frames == 1
            and native.budget.max_frame_bytes == native.budget.max_total_bytes,
            "CONFIGURATION_CAPTURE_EXACT_NATIVE_BUDGET",
        )
    frame_limit = native.budget.max_frames if purpose == "capture" else 0
    reg_budget = permit.registration.budget
    _require(
        reg_budget.maximum_reads == reg_budget.maximum_frames == frame_limit
        and reg_budget.maximum_writes == len(native.controls),
        "CAMERA_ACTIVATION_REGISTERED_NATIVE_LIMITS",
    )
    deadline = data["parent_deadline_ns"]
    _require(
        type(deadline) is int
        and permit.issued_at_ns < deadline <= permit.expires_at_ns
        and (
            expected_deadline_ns is None
            or type(expected_deadline_ns) is int
            and deadline == expected_deadline_ns
        ),
        "CAMERA_ACTIVATION_ORIGINAL_DEADLINE",
    )


@dataclass(frozen=True, slots=True)
class RetainedCameraActivationExecution:
    """An absent native receipt stays absent; returned evidence is still retained."""

    receipt: WorkerReceipt | None
    evidence: tuple[CameraActivationArtifact, ...]
    reason_codes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        checked = validate_camera_activation_evidence(self.evidence)
        _require(
            type(self.reason_codes) is tuple
            and len(self.reason_codes) <= 16
            and all(
                type(code) is str and bool(_REASON.fullmatch(code))
                for code in self.reason_codes
            )
            and len(set(self.reason_codes)) == len(self.reason_codes),
            "CAMERA_ACTIVATION_UNCERTAIN_REASONS",
        )
        native = checked.run.assessment().native
        if self.receipt is None:
            _require(
                native is None and bool(self.reason_codes),
                "CAMERA_UNKNOWN_RECEIPT_REQUIRES_UNAVAILABLE_COUNTS",
            )
        else:
            _require(
                type(self.receipt) is WorkerReceipt
                and native is not None
                and not self.reason_codes,
                "EXACT_CAMERA_ACTIVATION_WORKER_RECEIPT",
            )


def validate_camera_activation_execution(
    execution: RetainedCameraActivationExecution,
    permit: ExactOperationPermit,
    *,
    expected_deadline_ns: int,
) -> None:
    _require(
        type(execution) is RetainedCameraActivationExecution,
        "EXACT_CAMERA_ACTIVATION_EXECUTION",
    )
    execution.__post_init__()
    validate_camera_activation_binding(
        permit, execution.evidence, expected_deadline_ns=expected_deadline_ns
    )
    receipt = execution.receipt
    if receipt is None:
        return
    expected = _native_worker_receipt(
        permit, execution.evidence, expected_deadline_ns=expected_deadline_ns
    )
    assert expected is not None
    _match_native_camera_receipt(receipt, expected)


def validate_camera_activation_receipt(
    receipt: WorkerReceipt | None,
    permit: ExactOperationPermit,
    evidence: tuple[CameraActivationArtifact, ...],
    *,
    expected_deadline_ns: int,
) -> None:
    """Compare stored legacy accounting without manufacturing an execution.

    The store supplies its independently read permit, pair and receipt. Rebuild
    native accounting directly instead of constructing and then revalidating a
    candidate execution containing those same bytes. This caches no observation,
    changes no wire format and grants no permission or original-store provenance.
    """
    validate_camera_activation_binding(
        permit, evidence, expected_deadline_ns=expected_deadline_ns
    )
    expected = _native_worker_receipt(
        permit, evidence, expected_deadline_ns=expected_deadline_ns
    )
    _require(
        receipt is None or type(receipt) is WorkerReceipt,
        "EXACT_CAMERA_ACTIVATION_WORKER_RECEIPT",
    )
    _require(receipt == expected, "CAMERA_ACTIVATION_RECEIPT_ACCOUNTING_MISMATCH")
    if receipt is not None:
        assert expected is not None
        _match_native_camera_receipt(receipt, expected)


def _match_native_camera_receipt(
    receipt: WorkerReceipt, expected: WorkerReceipt
) -> None:
    # Equality alone treats True as 1; verify the exact scalar types too.
    _require(
        receipt == expected
        and receipt.effect_certainty is expected.effect_certainty
        and receipt.final_power_state is ObservedPowerState.UNKNOWN
        and type(receipt.cleanup_confirmed) is bool
        and all(
            type(getattr(receipt, name)) is int
            for name in ("opens", "reads", "writes", "frames", "closes", "output_bytes")
        )
        and type(receipt.evidence_sha256s) is tuple,
        "CAMERA_ACTIVATION_RECEIPT_ACCOUNTING_MISMATCH",
    )


def _native_worker_receipt(
    permit: ExactOperationPermit,
    evidence: tuple[CameraActivationArtifact, ...],
    *,
    expected_deadline_ns: int,
) -> WorkerReceipt | None:
    checked = validate_camera_activation_evidence(evidence)
    assessment = checked.run.assessment()
    native = assessment.native
    if native is None:
        return None
    data = checked.run.to_dict()
    started, finished = data["started_ns"], data["finished_ns"]
    timing = (
        type(started) is int
        and type(finished) is int
        and permit.issued_at_ns <= started <= finished < expected_deadline_ns
        and finished - started < permit.registration.budget.timeout_ms * 1_000_000
    )
    certainty = (
        EffectCertainty.CONFIRMED
        if assessment.status == "SUCCEEDED_NATIVE_DIAGNOSTIC" and timing
        else EffectCertainty.UNCERTAIN
    )
    return WorkerReceipt(
        permit.attempt_id,
        permit.permit_sha256,
        permit.registration.worker_executable_sha256,
        permit.admission.selected_identity_sha256,
        certainty,
        assessment.process_cleanup_confirmed and native.receipt.cleanup_confirmed,
        ObservedPowerState.UNKNOWN,
        native.receipt.counts["source_activation_attempts"],
        native.receipt.counts["samples_received"],
        native.receipt.counts["control_set_attempts"],
        native.receipt.counts["frames_written"],
        native.receipt.counts["source_shutdown_attempts"],
        sum(len(item.payload) for item in evidence),
        tuple(item.payload_sha256 for item in evidence),
        PHYSICAL_CAMERA_COMPOSITION,
    )


def camera_activation_execution(
    permit: ExactOperationPermit,
    evidence: tuple[CameraActivationArtifact, ...],
    *,
    expected_deadline_ns: int,
) -> RetainedCameraActivationExecution:
    """Build exact accounting from full native observations, never from claims.

    Pure conversion only. The original core/store still validate their own
    independently trusted permit, deadline, complete evidence and current scope.
    """
    validate_camera_activation_binding(
        permit, evidence, expected_deadline_ns=expected_deadline_ns
    )
    receipt = _native_worker_receipt(
        permit, evidence, expected_deadline_ns=expected_deadline_ns
    )
    return RetainedCameraActivationExecution(
        receipt,
        evidence,
        ("NATIVE_ACCOUNTING_UNAVAILABLE",) if receipt is None else (),
    )
