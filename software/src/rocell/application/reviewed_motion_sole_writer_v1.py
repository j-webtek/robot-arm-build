"""Hardware-incapable qualification of the reviewed motion sole writer.

This module closes the ARM-047 caller-acknowledgement gap without enabling live
motion.  It consumes one exact ``MotionPermit`` immediately before one bounded
in-memory write attempt, seals what was attempted and confirmed, and evaluates
fresh post-dispatch T=1051 feedback for arrival and settling.  Every claimed
session is single use.  Failure and uncertainty are terminal and never retry.

The I/O object in this module has no port, serial factory, callback, socket, or
device handle.  It is deliberately incapable of crossing a hardware boundary;
native enablement remains a separately reviewed milestone.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import hashlib
import json
import math
from threading import Lock
from typing import Any, Iterable, Mapping

from rocell.arm.feedback import Feedback1051, parse_feedback_1051
from rocell.arm.protocol import CartesianGoal, encode_line
from rocell.safety.permit import MotionPermit, goal_hash

from .reviewed_motion_permit_bridge_v1 import (
    ReviewedActionLifecycleV1,
    ReviewedMotionDispatchReceiptV1,
    ReviewedMotionPermitAdmissionV1,
    ReviewedMotionPermitBridgeError,
)


DISPATCH_SCHEMA = "rocell.reviewed_motion_dispatch_receipt.v1"
SETTLEMENT_SCHEMA = "rocell.reviewed_motion_settlement_evidence.v1"
EXECUTION_SCHEMA = "rocell.reviewed_motion_execution_rehearsal.v1"


class ReviewedMotionSoleWriterError(ValueError):
    """The exact reviewed writer contract was not satisfied."""


class IncapableWriteFault(str, Enum):
    NONE = "NONE"
    ZERO_WRITE = "ZERO_WRITE"
    PARTIAL_WRITE = "PARTIAL_WRITE"
    DISCONNECT_AFTER_WRITE = "DISCONNECT_AFTER_WRITE"


def _canonical(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")


def _sha256(value: object) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _bytes_sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _positive_ns(value: object, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ReviewedMotionSoleWriterError(f"{label} must be positive nanoseconds")
    return value


def _finite_nonnegative(value: object, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ReviewedMotionSoleWriterError(f"{label} must be finite and nonnegative")
    parsed = float(value)
    if not math.isfinite(parsed) or parsed < 0:
        raise ReviewedMotionSoleWriterError(f"{label} must be finite and nonnegative")
    return parsed


@dataclass(frozen=True, slots=True)
class SettlementPolicyV1:
    position_tolerance_mm: float = 2.0
    angle_tolerance_rad: float = 0.04
    required_consecutive_samples: int = 2
    max_feedback_age_ns: int = 500_000_000

    def __post_init__(self) -> None:
        object.__setattr__(self, "position_tolerance_mm", _finite_nonnegative(
            self.position_tolerance_mm, "position_tolerance_mm"))
        object.__setattr__(self, "angle_tolerance_rad", _finite_nonnegative(
            self.angle_tolerance_rad, "angle_tolerance_rad"))
        if (
            isinstance(self.required_consecutive_samples, bool)
            or not isinstance(self.required_consecutive_samples, int)
            or not 2 <= self.required_consecutive_samples <= 16
        ):
            raise ReviewedMotionSoleWriterError(
                "required_consecutive_samples must be between 2 and 16")
        _positive_ns(self.max_feedback_age_ns, "max_feedback_age_ns")


class IncapableReviewedMotionIoV1:
    """Single-owner byte sink with deterministic faults and no hardware API."""

    def __init__(self, fault: IncapableWriteFault = IncapableWriteFault.NONE) -> None:
        if not isinstance(fault, IncapableWriteFault):
            raise TypeError("fault must be IncapableWriteFault")
        self.fault = fault
        self._claimed = False
        self._attempts = 0
        self._retained = b""
        self._lock = Lock()

    def claim(self) -> None:
        with self._lock:
            if self._claimed:
                raise ReviewedMotionSoleWriterError(
                    "reviewed motion I/O is already claimed; retry is prohibited")
            self._claimed = True

    @property
    def write_attempts(self) -> int:
        return self._attempts

    @property
    def retained_bytes(self) -> bytes:
        return self._retained

    def _write_once(self, payload: bytes) -> int:
        """Owned internal boundary; public construction cannot reach hardware."""

        self._attempts += 1
        if self._attempts != 1:
            raise ReviewedMotionSoleWriterError("more than one write attempted")
        if self.fault is IncapableWriteFault.ZERO_WRITE:
            return 0
        if self.fault is IncapableWriteFault.PARTIAL_WRITE:
            count = max(0, len(payload) - 1)
            self._retained = payload[:count]
            return count
        self._retained = bytes(payload)
        if self.fault is IncapableWriteFault.DISCONNECT_AFTER_WRITE:
            raise ConnectionError("synthetic disconnect after full write")
        return len(payload)


def _dispatch_receipt(
    *, admission: ReviewedMotionPermitAdmissionV1, goal: CartesianGoal,
    payload: bytes, io: IncapableReviewedMotionIoV1, confirmed_bytes: int | None,
    dispatched_monotonic_ns: int, error_code: str | None,
) -> ReviewedMotionDispatchReceiptV1:
    if confirmed_bytes == len(payload) and error_code is None:
        status = "REPLAY_WRITE_CONFIRMED"
    elif confirmed_bytes == 0 and error_code is None:
        status = "ZERO_WRITE_CONFIRMED"
    elif confirmed_bytes is not None and 0 < confirmed_bytes < len(payload):
        status = "PARTIAL_WRITE_CONFIRMED"
    else:
        status = "WRITE_COMPLETION_UNCERTAIN"
    report = {
        "schema": DISPATCH_SCHEMA,
        "status": status,
        "review_sha256": admission.review_sha256,
        "permit_binding_sha256": admission.permit_binding_sha256,
        "goal_sha256": goal_hash(goal),
        "payload_sha256": _bytes_sha256(payload),
        "payload_bytes": len(payload),
        "confirmed_bytes": confirmed_bytes,
        "retained_bytes_sha256": _bytes_sha256(io.retained_bytes),
        "write_attempts": io.write_attempts,
        "permit_consumed": True,
        "dispatched_monotonic_ns": dispatched_monotonic_ns,
        "error_code": error_code,
        "composition": "HARDWARE_INCAPABLE_REPLAY",
        "automatic_retry_allowed": False,
        "hardware_access": False,
        "physical_authority": False,
        "physical_command_writes": 0,
    }
    document = {**report, "dispatch_receipt_sha256": _sha256(report)}
    return ReviewedMotionDispatchReceiptV1._issue_from_owned_writer(document)


def _feedback_values(feedback: Feedback1051) -> tuple[float | None, ...]:
    return (
        feedback.x_mm, feedback.y_mm, feedback.z_mm,
        feedback.endpoint_pitch_rad, feedback.wrist_roll_rad,
        feedback.gripper_rad,
    )


def _goal_values(goal: CartesianGoal) -> tuple[float, ...]:
    return (
        goal.x_mm, goal.y_mm, goal.z_mm, goal.pitch_rad,
        goal.roll_rad, goal.gripper_rad,
    )


def assess_settlement_v1(
    dispatch_receipt: Mapping[str, Any], goal: CartesianGoal,
    feedback_samples: Iterable[Mapping[str, Any]], *, policy: SettlementPolicyV1,
    assessed_monotonic_ns: int,
) -> dict[str, Any]:
    """Require fresh, ordered, consecutive in-tolerance post-write feedback."""

    if not isinstance(policy, SettlementPolicyV1):
        raise TypeError("policy must be SettlementPolicyV1")
    assessed = _positive_ns(assessed_monotonic_ns, "assessed_monotonic_ns")
    dispatch_ns = _positive_ns(
        dispatch_receipt.get("dispatched_monotonic_ns"),
        "dispatched_monotonic_ns",
    )
    accepted: list[tuple[int, tuple[float, ...], str, int]] = []
    rejected_codes: list[str] = []
    previous_ns = dispatch_ns
    sequence_group = 0
    for sample in feedback_samples:
        if not isinstance(sample, Mapping):
            rejected_codes.append("MALFORMED_SAMPLE")
            sequence_group += 1
            continue
        captured = sample.get("captured_monotonic_ns")
        message = sample.get("message")
        if (
            isinstance(captured, bool) or not isinstance(captured, int)
            or captured <= previous_ns
        ):
            rejected_codes.append("NON_MONOTONIC_OR_PRE_DISPATCH")
            sequence_group += 1
            continue
        previous_ns = captured
        if captured > assessed or assessed - captured > policy.max_feedback_age_ns:
            rejected_codes.append("STALE_OR_FUTURE_FEEDBACK")
            sequence_group += 1
            continue
        try:
            parsed = parse_feedback_1051(message)
        except Exception:
            rejected_codes.append("INVALID_T1051")
            sequence_group += 1
            continue
        values = _feedback_values(parsed)
        if any(value is None for value in values):
            rejected_codes.append("INCOMPLETE_POSE")
            sequence_group += 1
            continue
        numeric = tuple(float(value) for value in values if value is not None)
        accepted.append((captured, numeric, _sha256(dict(message)), sequence_group))

    target = _goal_values(goal)
    consecutive = 0
    max_position_error = 0.0
    max_angle_error = 0.0
    previous_values: tuple[float, ...] | None = None
    previous_group: int | None = None
    for _, values, _, group in accepted:
        position_error = max(abs(values[i] - target[i]) for i in range(3))
        angle_error = max(abs(values[i] - target[i]) for i in range(3, 6))
        max_position_error = max(max_position_error, position_error)
        max_angle_error = max(max_angle_error, angle_error)
        stable = previous_values is None or previous_group != group or (
            max(abs(values[i] - previous_values[i]) for i in range(3))
            <= policy.position_tolerance_mm
            and max(abs(values[i] - previous_values[i]) for i in range(3, 6))
            <= policy.angle_tolerance_rad
        )
        if previous_group != group:
            consecutive = 0
        if (
            position_error <= policy.position_tolerance_mm
            and angle_error <= policy.angle_tolerance_rad
            and stable
        ):
            consecutive += 1
        else:
            consecutive = 0
        previous_values = values
        previous_group = group

    settled = consecutive >= policy.required_consecutive_samples
    status = "OBSERVED_SETTLED_ARRIVAL" if settled else "ARRIVAL_UNVERIFIED"
    report = {
        "schema": SETTLEMENT_SCHEMA,
        "status": status,
        "dispatch_receipt_sha256": dispatch_receipt["dispatch_receipt_sha256"],
        "goal_sha256": goal_hash(goal),
        "assessed_monotonic_ns": assessed,
        "accepted_sample_count": len(accepted),
        "rejected_sample_codes": rejected_codes,
        "consecutive_settled_samples": consecutive,
        "required_consecutive_samples": policy.required_consecutive_samples,
        "position_tolerance_mm": policy.position_tolerance_mm,
        "angle_tolerance_rad": policy.angle_tolerance_rad,
        "max_position_error_mm": max_position_error,
        "max_angle_error_rad": max_angle_error,
        "feedback_message_sha256": [item[2] for item in accepted],
        "controller_receipt_claimed": False,
        "independent_outcome_verified": False,
    }
    return {**report, "settlement_sha256": _sha256(report)}


def execute_reviewed_motion_rehearsal_v1(
    goal: CartesianGoal, permit: MotionPermit,
    admission: ReviewedMotionPermitAdmissionV1,
    lifecycle: ReviewedActionLifecycleV1,
    io: IncapableReviewedMotionIoV1,
    feedback_samples: Iterable[Mapping[str, Any]] = (), *,
    settlement_policy: SettlementPolicyV1 = SettlementPolicyV1(),
    now_monotonic: float, dispatched_monotonic_ns: int,
    assessed_monotonic_ns: int,
) -> dict[str, Any]:
    """Consume, write once in memory, settle, and terminate without retry."""

    if not isinstance(goal, CartesianGoal):
        raise TypeError("goal must be CartesianGoal")
    if not isinstance(permit, MotionPermit):
        raise TypeError("permit must be MotionPermit")
    if not isinstance(admission, ReviewedMotionPermitAdmissionV1):
        raise TypeError("admission must be ReviewedMotionPermitAdmissionV1")
    if not isinstance(lifecycle, ReviewedActionLifecycleV1):
        raise TypeError("lifecycle must be ReviewedActionLifecycleV1")
    if type(io) is not IncapableReviewedMotionIoV1:
        raise TypeError("exact hardware-incapable I/O is required")
    dispatch_ns = _positive_ns(dispatched_monotonic_ns, "dispatched_monotonic_ns")
    assessed_ns = _positive_ns(assessed_monotonic_ns, "assessed_monotonic_ns")
    if assessed_ns < dispatch_ns:
        raise ReviewedMotionSoleWriterError("assessment precedes dispatch")
    digest = goal_hash(goal)
    if (
        digest not in admission.ordered_goal_sha256
        or permit.plan_hash != admission.review_sha256
        or permit.snapshot_hash != admission.snapshot_sha256
        or permit.expires_at_monotonic != admission.permit_expires_at_monotonic
    ):
        raise ReviewedMotionSoleWriterError("permit/admission/goal binding mismatch")
    payload = encode_line(goal.to_message())
    io.claim()
    if permit.allows(goal, now_monotonic=now_monotonic) is not True:
        raise ReviewedMotionSoleWriterError(
            "exact permit was not consumable; no write attempted")

    confirmed: int | None = None
    error_code: str | None = None
    try:
        confirmed = io._write_once(payload)
    except ConnectionError:
        error_code = "DISCONNECT_AFTER_WRITE"
    except Exception as exc:
        error_code = type(exc).__name__.upper()
    typed_receipt = _dispatch_receipt(
        admission=admission, goal=goal, payload=payload, io=io,
        confirmed_bytes=confirmed, dispatched_monotonic_ns=dispatch_ns,
        error_code=error_code,
    )
    lifecycle.started_from_dispatch(typed_receipt, event_monotonic_ns=dispatch_ns)
    receipt = typed_receipt.to_dict()

    settlement: dict[str, Any] | None = None
    if receipt["status"] == "REPLAY_WRITE_CONFIRMED":
        settlement = assess_settlement_v1(
            receipt, goal, feedback_samples, policy=settlement_policy,
            assessed_monotonic_ns=assessed_ns,
        )
        terminal = (
            "COMPLETED"
            if settlement["status"] == "OBSERVED_SETTLED_ARRIVAL"
            else "UNCERTAIN"
        )
        detail_sha256 = settlement["settlement_sha256"]
    elif receipt["status"] == "ZERO_WRITE_CONFIRMED":
        terminal = "FAILED"
        detail_sha256 = receipt["dispatch_receipt_sha256"]
    else:
        terminal = "UNCERTAIN"
        detail_sha256 = receipt["dispatch_receipt_sha256"]
    lifecycle.terminal(
        terminal, detail_sha256=detail_sha256,
        event_monotonic_ns=assessed_ns,
    )
    lifecycle_snapshot = lifecycle.snapshot()
    report = {
        "schema": EXECUTION_SCHEMA,
        "status": terminal,
        "permit_binding_sha256": admission.permit_binding_sha256,
        "dispatch": receipt,
        "settlement": settlement,
        "lifecycle": lifecycle_snapshot,
        "automatic_retry_allowed": False,
        "follow_on_movement_authorized": False,
        "hardware_access": False,
        "physical_authority": False,
        "physical_command_writes": 0,
        "limitations": [
            "HARDWARE_INCAPABLE_REPLAY",
            "NO_AUTHENTIC_CONTROLLER_RECEIPT",
            "NO_INDEPENDENT_TASK_OUTCOME",
        ],
    }
    return {**report, "execution_sha256": _sha256(report)}


__all__ = [
    "DISPATCH_SCHEMA", "EXECUTION_SCHEMA", "SETTLEMENT_SCHEMA",
    "IncapableReviewedMotionIoV1", "IncapableWriteFault",
    "ReviewedMotionSoleWriterError", "SettlementPolicyV1",
    "assess_settlement_v1", "execute_reviewed_motion_rehearsal_v1",
]
