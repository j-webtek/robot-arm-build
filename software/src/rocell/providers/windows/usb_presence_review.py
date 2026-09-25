"""Pure exact-subject review of presence policy and intended runtime.

Nothing here reads files, observes devices, starts processes or issues authority.
The original-store owner independently authenticates the retained review bytes,
reference and committed review event. Its hash then enters the consumed permit;
a caller-supplied expected hash is not original trust.

Operation precedes review. Neither operation nor phase identity references this
review or the later permit, so no hash cycle is formed.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, cast

from rocell.application.physical_usb_presence_binding import UsbPresencePhaseBinding
from rocell.application.usb_presence_stage_policy import (
    UsbPresenceStagePolicy,
    usb_presence_stage_policy,
)
from .owned_worker_process import decode_owned_json
from .usb_presence_protocol import canonical, digest
from .usb_presence_registration import (
    IncapableUsbPresenceRuntimeRegistration,
    UsbPresenceRuntimeRegistration,
)

REVIEW_SCHEMA = "rocell.usb_presence_runtime_review.v1"
MAX_REVIEW_BYTES = 8 * 1024
DECISION = "ACKNOWLEDGE_EXACT_USB_PRESENCE_POLICY_AND_RUNTIME"
Runtime = UsbPresenceRuntimeRegistration | IncapableUsbPresenceRuntimeRegistration
_SHA = re.compile(r"[0-9a-f]{64}\Z")
_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}\Z")
_HASH_FIELDS = {
    "source_sha256",
    "header_sha256",
    "phase_binding_sha256",
    "target_instance_id_sha256",
    "runtime_registration_sha256",
    "helper_sha256",
    "usb_presence_policy_sha256",
    "operation_sha256",
}
_FALSE_FLAGS = {
    "authenticated_independent_people",
    "physical_authority",
    "hardware_qualified",
    "camera_capture_authorized",
    "arm_access_authorized",
}
_FIELDS = {
    "schema",
    "cell_id",
    "session_id",
    "trial_id",
    "phase",
    "operator_id",
    "reviewer_id",
    "launch_session_id",
    "reviewed_at_ns",
    "decision",
    "distinct_operator_labels",
    *_HASH_FIELDS,
    *_FALSE_FLAGS,
}


class UsbPresenceReviewError(ValueError):
    """Fixed mismatch code; never raw operator/native diagnostic text."""

    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


def _need(ok: bool, code: str) -> None:
    if not ok:
        raise UsbPresenceReviewError(code)


def _sha(value: Any) -> None:
    _need(
        type(value) is str and bool(_SHA.fullmatch(value)) and value != "0" * 64,
        "NONZERO_REVIEW_SHA256_REQUIRED",
    )


def _label(value: Any) -> None:
    _need(
        type(value) is str
        and 1 <= len(value) <= 64
        and value == value.strip()
        and all(32 <= ord(char) <= 126 for char in value),
        "EXACT_BOUNDED_REVIEW_LABEL_REQUIRED",
    )


def _document(payload: bytes) -> dict[str, Any]:
    try:
        value = decode_owned_json(payload, maximum=MAX_REVIEW_BYTES)
        _need(
            set(value) == _FIELDS and canonical(value) == payload,
            "EXACT_CANONICAL_PRESENCE_REVIEW_REQUIRED",
        )
        _need(
            value["schema"] == REVIEW_SCHEMA
            and value["decision"] == DECISION
            and value["phase"] == "RECONNECT_ABSENCE"
            and value["distinct_operator_labels"] is True
            and all(value[key] is False for key in _FALSE_FLAGS),
            "EXACT_PRESENCE_REVIEW_MEANING_REQUIRED",
        )
        for name in _HASH_FIELDS:
            _sha(value[name])
        _need(
            value["usb_presence_policy_sha256"] == usb_presence_stage_policy().sha256,
            "FIXED_PRESENCE_POLICY_REQUIRED",
        )
        for name, pattern in (
            ("cell_id", r"wizard-physical-camera-[0-9a-f]{16}"),
            ("session_id", r"physical-camera-[0-9a-f]{32}"),
            ("trial_id", r"usbtrial-[0-9a-f]{32}"),
        ):
            _need(
                type(value[name]) is str
                and re.fullmatch(pattern, value[name]) is not None,
                "EXACT_ORIGINAL_REVIEW_CONTEXT_REQUIRED",
            )
        _need(
            type(value["launch_session_id"]) is str
            and bool(_ID.fullmatch(value["launch_session_id"])),
            "EXACT_REVIEW_LAUNCH_REQUIRED",
        )
        _label(value["operator_id"])
        _label(value["reviewer_id"])
        _need(
            value["operator_id"].casefold() != value["reviewer_id"].casefold(),
            "DISTINCT_REVIEW_LABELS_REQUIRED",
        )
        _need(
            type(value["reviewed_at_ns"]) is int
            and 0 < value["reviewed_at_ns"] < 2**63,
            "EXACT_REVIEW_TIME_REQUIRED",
        )
        return value
    except UsbPresenceReviewError:
        raise
    except (ValueError, TypeError, KeyError, AttributeError, RecursionError) as exc:
        raise UsbPresenceReviewError("INVALID_PRESENCE_REVIEW") from exc


@dataclass(frozen=True, slots=True)
class UsbPresenceRuntimeReview:
    """Immutable review bytes; construction does not authenticate approval."""

    payload: bytes

    def __post_init__(self) -> None:
        _document(self.payload)

    @property
    def sha256(self) -> str:
        return digest(self.payload)

    def to_dict(self) -> dict[str, Any]:
        return _document(self.payload)


def review_usb_presence_runtime(
    runtime: Runtime,
    *,
    phase_binding: UsbPresencePhaseBinding,
    policy: UsbPresenceStagePolicy,
    operation_sha256: str,
    operator_id: str,
    reviewer_id: str,
    launch_session_id: str,
    reviewed_at_ns: int,
) -> UsbPresenceRuntimeReview:
    """Bind explicit labels to immutable subjects without inspecting them.

    The application supplies its original pre-review operation hash. This pure
    function cannot infer current original storage, completed file inspection,
    independent people, or permission to perform the later observation.
    """
    try:
        _need(
            type(runtime)
            in (UsbPresenceRuntimeRegistration, IncapableUsbPresenceRuntimeRegistration)
            and type(phase_binding) is UsbPresencePhaseBinding
            and type(policy) is UsbPresenceStagePolicy,
            "EXACT_PRESENCE_REVIEW_SUBJECTS_REQUIRED",
        )
        runtime = type(runtime)(runtime.payload)
        phase_binding = UsbPresencePhaseBinding(phase_binding.payload)
        policy = UsbPresenceStagePolicy(policy.payload)
        r, phase = runtime.to_dict(), phase_binding.to_dict()
        binding = phase["binding"]
        _need(
            r["source_sha256"] == binding["source_sha256"],
            "PRESENCE_REVIEW_SOURCE_MISMATCH",
        )
        _need(
            type(reviewed_at_ns) is int
            and phase["not_before_utc_ns"] <= reviewed_at_ns < 2**63,
            "REVIEW_AFTER_ORIGINAL_BASELINE_REQUIRED",
        )
        return UsbPresenceRuntimeReview(
            canonical(
                dict(
                    schema=REVIEW_SCHEMA,
                    **{
                        key: binding[key]
                        for key in (
                            "source_sha256",
                            "cell_id",
                            "session_id",
                            "header_sha256",
                            "trial_id",
                        )
                    },
                    phase=phase["phase"],
                    phase_binding_sha256=phase_binding.sha256,
                    target_instance_id_sha256=phase["target"][
                        "physical_usb_instance_id_sha256"
                    ],
                    runtime_registration_sha256=runtime.sha256,
                    helper_sha256=r["helper"]["sha256"],
                    usb_presence_policy_sha256=policy.sha256,
                    operation_sha256=operation_sha256,
                    operator_id=operator_id,
                    reviewer_id=reviewer_id,
                    launch_session_id=launch_session_id,
                    reviewed_at_ns=reviewed_at_ns,
                    decision=DECISION,
                    distinct_operator_labels=True,
                    **dict.fromkeys(_FALSE_FLAGS, False),
                )
            )
        )
    except UsbPresenceReviewError:
        raise
    except (ValueError, TypeError, KeyError, AttributeError, RecursionError) as exc:
        raise UsbPresenceReviewError("INVALID_PRESENCE_REVIEW_SUBJECTS") from exc


def verify_usb_presence_runtime_review(
    value: bytes | UsbPresenceRuntimeReview,
    *,
    runtime: Runtime,
    phase_binding: UsbPresencePhaseBinding,
    policy: UsbPresenceStagePolicy,
    operation_sha256: str,
    expected_review_sha256: str,
) -> UsbPresenceRuntimeReview:
    """Reconstruct exactly against independently supplied original subjects/hash."""
    _sha(expected_review_sha256)
    _need(
        type(value) in (bytes, UsbPresenceRuntimeReview),
        "EXACT_REVIEW_BYTES_OR_TYPE_REQUIRED",
    )
    payload = (
        value.payload if type(value) is UsbPresenceRuntimeReview else cast(bytes, value)
    )
    review = UsbPresenceRuntimeReview(payload)
    _need(review.sha256 == expected_review_sha256, "ORIGINAL_REVIEW_HASH_MISMATCH")
    data = review.to_dict()
    rebuilt = review_usb_presence_runtime(
        runtime,
        phase_binding=phase_binding,
        policy=policy,
        operation_sha256=operation_sha256,
        operator_id=data["operator_id"],
        reviewer_id=data["reviewer_id"],
        launch_session_id=data["launch_session_id"],
        reviewed_at_ns=data["reviewed_at_ns"],
    )
    _need(
        review.payload == rebuilt.payload, "EXACT_REVIEW_SUBJECT_RECONSTRUCTION_FAILED"
    )
    return review
