"""Original-permit and receipt accounting for checksum-bearing capture v2.

This profile retains native physical counts unchanged. A failed file read makes
the full operation uncertain; it never invents zero camera effects or causes a
new capture. No plan, permit issuance, process creation or storage is done here.
"""

from dataclasses import dataclass, replace

from .camera_activation_campaign_contract import (
    SEALED_CONFIGURATION_CAPTURE_ACTION_ID,
    _validate_camera_activation_native_binding,
    _native_worker_receipt,
    _REASON,
)
from .camera_activation_campaign_evidence import validate_camera_activation_evidence
from .camera_sealed_capture_evidence import SealedCameraCaptureEvidence
from .cell_commissioning_coordinator import (
    ExactOperationPermit,
    WorkerReceipt,
    ObservedPowerState,
)
from rocell.providers.windows.native_camera_protocol import _require
from rocell.safety.effects import EffectCertainty


def is_sealed_capture(permit):
    return (
        type(permit) is ExactOperationPermit
        and permit.registration.action_id == SEALED_CONFIGURATION_CAPTURE_ACTION_ID
    )


def validate_sealed_capture_binding(permit, evidence, *, expected_deadline_ns=None):
    _require(is_sealed_capture(permit), "EXACT_SEALED_CAPTURE_PERMIT")
    _require(
        type(evidence) is SealedCameraCaptureEvidence, "EXACT_SEALED_CAPTURE_COLLECTION"
    )
    evidence.__post_init__()
    _validate_camera_activation_native_binding(
        permit, evidence.native, expected_deadline_ns=expected_deadline_ns
    )
    # __post_init__ independently rebuilt this checksum from these native bytes.
    # The original permit contributes one additional checksum input: request key.
    # Compare it directly rather than rebuilding the same native join a second
    # time. No original-store/currentness boundary is removed or cached.
    _require(
        evidence.checksum.to_dict()["request_key"] == permit.request.request_key,
        "SEALED_CAPTURE_ORIGINAL_REQUEST_KEY",
    )


def _execution_shape(execution):
    """Closed scalar/type checks, independent of native semantic reconstruction."""
    _require(
        type(execution.evidence) is SealedCameraCaptureEvidence,
        "EXACT_SEALED_CAPTURE_COLLECTION",
    )
    _require(
        execution.receipt is None or type(execution.receipt) is WorkerReceipt,
        "EXACT_SEALED_CAPTURE_RECEIPT",
    )
    _require(
        type(execution.reason_codes) is tuple
        and len(execution.reason_codes) <= 16
        and all(
            type(code) is str and bool(_REASON.fullmatch(code))
            for code in execution.reason_codes
        )
        and len(set(execution.reason_codes)) == len(execution.reason_codes),
        "SEALED_CAPTURE_UNCERTAIN_REASONS",
    )


@dataclass(frozen=True, slots=True)
class RetainedSealedCaptureExecution:
    receipt: WorkerReceipt | None
    evidence: SealedCameraCaptureEvidence
    reason_codes: tuple[str, ...] = ()

    def __post_init__(self):
        _execution_shape(self)
        self.evidence.__post_init__()
        native = (
            validate_camera_activation_evidence(self.evidence.native)
            .run.assessment()
            .native
        )
        if self.receipt is None:
            _require(
                native is None and bool(self.reason_codes),
                "SEALED_CAPTURE_NATIVE_COUNTS_UNAVAILABLE",
            )
        else:
            _require(
                type(self.receipt) is WorkerReceipt
                and native is not None
                and not self.reason_codes,
                "EXACT_SEALED_CAPTURE_RECEIPT",
            )


def sealed_capture_execution(permit, evidence, *, expected_deadline_ns):
    validate_sealed_capture_binding(
        permit, evidence, expected_deadline_ns=expected_deadline_ns
    )
    native_receipt = _native_worker_receipt(
        permit, evidence.native, expected_deadline_ns=expected_deadline_ns
    )
    if native_receipt is None:
        return RetainedSealedCaptureExecution(
            None, evidence, ("NATIVE_ACCOUNTING_UNAVAILABLE",)
        )
    verified = evidence.checksum.to_dict()["status"] == "CAPTURE_BYTES_HASHED"
    receipt = replace(
        native_receipt,
        output_bytes=evidence.payload_bytes,
        evidence_sha256s=evidence.evidence_sha256s,
        # The combined receipt cannot claim file-scope cleanup from the older
        # native cleanup bit. A non-successful checksum read withholds it.
        cleanup_confirmed=native_receipt.cleanup_confirmed and verified,
        effect_certainty=(
            native_receipt.effect_certainty if verified else EffectCertainty.UNCERTAIN
        ),
    )
    return RetainedSealedCaptureExecution(receipt, evidence)


def validate_sealed_capture_execution(execution, permit, *, expected_deadline_ns):
    _require(
        type(execution) is RetainedSealedCaptureExecution,
        "EXACT_SEALED_CAPTURE_EXECUTION",
    )
    _execution_shape(execution)
    # Reconstruct the complete expected execution from these exact bytes and the
    # original permit. Its constructor rechecks native availability and all
    # collection semantics. Comparing it below therefore covers those same
    # semantic constraints without first doing another full constructor decode.
    # Exact scalar types remain checked separately: equality alone accepts 1/True.
    expected = sealed_capture_execution(
        permit, execution.evidence, expected_deadline_ns=expected_deadline_ns
    )
    _require(execution == expected, "SEALED_CAPTURE_RECEIPT_MISMATCH")
    _match_sealed_receipt(execution.receipt, expected.receipt)


def validate_sealed_capture_receipt(receipt, permit, evidence, *, expected_deadline_ns):
    """Authenticate a stored receipt against one freshly reconstructed execution.

    The store has receipt bytes, not a supplied execution object. Constructing a
    candidate execution merely to validate it against another reconstruction
    repeats the same native availability/collection decode. Rebuild the expected
    execution directly; no native, permit, accounting or scalar check is cached.
    """
    expected = sealed_capture_execution(
        permit, evidence, expected_deadline_ns=expected_deadline_ns
    )
    _match_sealed_receipt(receipt, expected.receipt)


def _match_sealed_receipt(receipt, expected):
    _require(
        receipt is None or type(receipt) is WorkerReceipt,
        "EXACT_SEALED_CAPTURE_RECEIPT",
    )
    _require(receipt == expected, "SEALED_CAPTURE_RECEIPT_MISMATCH")
    if receipt is not None:
        # Dataclass equality would otherwise equate True with integer 1.
        _require(
            receipt.effect_certainty is expected.effect_certainty
            and receipt.final_power_state is ObservedPowerState.UNKNOWN
            and type(receipt.cleanup_confirmed) is bool
            and all(
                type(getattr(receipt, name)) is int
                for name in (
                    "opens",
                    "reads",
                    "writes",
                    "frames",
                    "closes",
                    "output_bytes",
                )
            )
            and type(receipt.evidence_sha256s) is tuple,
            "SEALED_CAPTURE_RECEIPT_TYPES",
        )
