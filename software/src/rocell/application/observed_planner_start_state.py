"""Authenticated T=1051 feedback projected into calibrated planner joints.

This adapter is deliberately read-only.  It accepts an already completed,
single-query feedback receipt and its exact request, verifies their identity and
freshness lineage, then applies the measured robot-reference projection
``q_model = sign*q_feedback + offset``.  It creates no controller command and
owns no physical authority.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
import re
from types import MappingProxyType
from typing import Any, Mapping

from rocell.arm import parse_feedback_line
from rocell.calibration import PlannerCalibrationSnapshot
from rocell.kinematics import ARM_JOINT_NAMES

from .physical_connection_contracts import (
    SingleT105FeedbackReceipt,
    SingleT105FeedbackRequest,
)


SCHEMA = "rocell.observed_planner_start_state.v1"
REFERENCE_JOINT_ORDER = (
    "b_base",
    "s_shoulder",
    "e_elbow",
    "t_wrist_pitch",
    "r_wrist_roll",
    "g_gripper",
)
FEEDBACK_FIELDS = ("b", "s", "e", "t", "r", "g")
_FEEDBACK_ATTRIBUTES = (
    "base_rad",
    "shoulder_rad",
    "elbow_rad",
    "wrist_pitch_rad",
    "wrist_roll_rad",
    "gripper_rad",
)
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class ObservedPlannerStartStateError(ValueError):
    """Feedback cannot qualify as the current calibrated planner state."""


def _canonical(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
    ).encode("utf-8")


def _positive_int(value: object, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ObservedPlannerStartStateError(f"{label} must be a positive integer")
    return value


def _digest(value: object, label: str) -> str:
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        raise ObservedPlannerStartStateError(f"{label} must be a SHA-256 digest")
    return value


def _joint_mapping(
    value: Mapping[str, float], expected: tuple[str, ...], label: str
) -> MappingProxyType:
    if not isinstance(value, Mapping) or set(value) != set(expected):
        raise ObservedPlannerStartStateError(
            f"{label} must contain exactly {','.join(expected)}"
        )
    normalized: dict[str, float] = {}
    for name in expected:
        raw = value[name]
        if isinstance(raw, bool) or not isinstance(raw, (int, float)):
            raise ObservedPlannerStartStateError(f"{label}.{name} must be numeric")
        number = float(raw)
        if not math.isfinite(number):
            raise ObservedPlannerStartStateError(f"{label}.{name} must be finite")
        normalized[name] = number
    return MappingProxyType(normalized)


@dataclass(frozen=True, slots=True)
class ObservedPlannerStartState:
    run_id: str
    arm_identity_sha256: str
    controller_session_id: str
    request_context_sha256: str
    feedback_receipt_sha256: str
    calibration_snapshot_sha256: str
    manifest_id: str
    active_build_id: str
    response_completed_monotonic_ns: int
    available_monotonic_ns: int
    valid_until_monotonic_ns: int
    controller_joint_positions_rad: Mapping[str, float]
    model_joint_positions_rad: Mapping[str, float]

    def __post_init__(self) -> None:
        for name in ("run_id", "controller_session_id", "manifest_id", "active_build_id"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ObservedPlannerStartStateError(f"{name} must be nonempty text")
        for name in (
            "arm_identity_sha256",
            "request_context_sha256",
            "feedback_receipt_sha256",
            "calibration_snapshot_sha256",
        ):
            _digest(getattr(self, name), name)
        completed = _positive_int(
            self.response_completed_monotonic_ns,
            "response_completed_monotonic_ns",
        )
        available = _positive_int(self.available_monotonic_ns, "available_monotonic_ns")
        valid_until = _positive_int(
            self.valid_until_monotonic_ns, "valid_until_monotonic_ns"
        )
        if not completed <= available <= valid_until:
            raise ObservedPlannerStartStateError(
                "observed-state timing must be response <= available <= expiry"
            )
        object.__setattr__(
            self,
            "controller_joint_positions_rad",
            _joint_mapping(
                self.controller_joint_positions_rad,
                FEEDBACK_FIELDS,
                "controller_joint_positions_rad",
            ),
        )
        object.__setattr__(
            self,
            "model_joint_positions_rad",
            _joint_mapping(
                self.model_joint_positions_rad,
                REFERENCE_JOINT_ORDER,
                "model_joint_positions_rad",
            ),
        )

    @property
    def arm_joint_positions_rad(self) -> Mapping[str, float]:
        return MappingProxyType(
            {
                name: self.model_joint_positions_rad[reference]
                for name, reference in zip(
                    ARM_JOINT_NAMES, REFERENCE_JOINT_ORDER[:5], strict=True
                )
            }
        )

    def require_fresh_for(
        self,
        snapshot: PlannerCalibrationSnapshot,
        evaluation_monotonic_ns: int,
    ) -> Mapping[str, float]:
        """Return the five IK joints only while lineage and freshness still hold."""

        if not isinstance(snapshot, PlannerCalibrationSnapshot):
            raise TypeError("snapshot must be a PlannerCalibrationSnapshot")
        now = _positive_int(evaluation_monotonic_ns, "evaluation_monotonic_ns")
        if self.calibration_snapshot_sha256 != snapshot.snapshot_sha256:
            raise ObservedPlannerStartStateError(
                "observed state is bound to a different calibration snapshot"
            )
        if (
            self.manifest_id != snapshot.manifest_id
            or self.active_build_id != snapshot.active_build_id
        ):
            raise ObservedPlannerStartStateError(
                "observed state build identity differs from planner calibration"
            )
        if now < self.available_monotonic_ns:
            raise ObservedPlannerStartStateError(
                "planner evaluation predates completion of feedback acquisition"
            )
        if now > self.valid_until_monotonic_ns:
            raise ObservedPlannerStartStateError("observed planner start state is stale")
        return self.arm_joint_positions_rad

    def to_dict(self) -> dict[str, Any]:
        report: dict[str, Any] = {
            "schema": SCHEMA,
            "status": "READY_FOR_OFFLINE_TRAJECTORY_SCREENING",
            "source": {
                "run_id": self.run_id,
                "arm_identity_sha256": self.arm_identity_sha256,
                "controller_session_id": self.controller_session_id,
                "request_context_sha256": self.request_context_sha256,
                "feedback_receipt_sha256": self.feedback_receipt_sha256,
            },
            "calibration": {
                "calibration_snapshot_sha256": self.calibration_snapshot_sha256,
                "manifest_id": self.manifest_id,
                "active_build_id": self.active_build_id,
                "projection": "q_model=sign*q_feedback+offset",
            },
            "freshness": {
                "response_completed_monotonic_ns": self.response_completed_monotonic_ns,
                "available_monotonic_ns": self.available_monotonic_ns,
                "valid_until_monotonic_ns": self.valid_until_monotonic_ns,
            },
            "controller_joint_positions_rad": dict(
                self.controller_joint_positions_rad
            ),
            "model_joint_positions_rad": dict(self.model_joint_positions_rad),
            "arm_joint_positions_rad": dict(self.arm_joint_positions_rad),
            "controller_commands": [],
            "hardware_commands_generated": 0,
            "hardware_access": False,
            "physical_authority": False,
        }
        return {
            **report,
            "observed_start_state_sha256": hashlib.sha256(_canonical(report)).hexdigest(),
        }

    @property
    def observed_start_state_sha256(self) -> str:
        return self.to_dict()["observed_start_state_sha256"]


def build_observed_planner_start_state(
    request: SingleT105FeedbackRequest,
    receipt: SingleT105FeedbackReceipt,
    snapshot: PlannerCalibrationSnapshot,
    *,
    observed_monotonic_ns: int,
    maximum_age_ns: int,
) -> ObservedPlannerStartState:
    """Authenticate, calibrate, bound, and freshness-limit one complete joint read."""

    if not isinstance(request, SingleT105FeedbackRequest):
        raise TypeError("request must be a SingleT105FeedbackRequest")
    if not isinstance(receipt, SingleT105FeedbackReceipt):
        raise TypeError("receipt must be a SingleT105FeedbackReceipt")
    if not isinstance(snapshot, PlannerCalibrationSnapshot):
        raise TypeError("snapshot must be a PlannerCalibrationSnapshot")
    now = _positive_int(observed_monotonic_ns, "observed_monotonic_ns")
    maximum_age = _positive_int(maximum_age_ns, "maximum_age_ns")
    if request.request_context_sha256 != receipt.request_context_sha256:
        raise ObservedPlannerStartStateError("receipt does not bind the exact T=105 request")
    if (
        request.run_id != receipt.run_id
        or request.arm_identity_sha256 != receipt.arm_identity_sha256
        or request.controller_session_id != receipt.controller_session_id
    ):
        raise ObservedPlannerStartStateError(
            "feedback receipt identity differs from its request"
        )
    if receipt.timing.port_opened_monotonic_ns < request.requested_monotonic_ns:
        raise ObservedPlannerStartStateError(
            "feedback transaction predates its bound T=105 request"
        )
    calibrated_arm = snapshot.robot_reference_identity["arm_identity_hash"]
    if receipt.arm_identity_sha256 != calibrated_arm:
        raise ObservedPlannerStartStateError(
            "feedback arm identity differs from calibrated robot reference"
        )
    completed = receipt.timing.response_completed_monotonic_ns
    available = receipt.timing.port_closed_monotonic_ns
    if now < available:
        raise ObservedPlannerStartStateError(
            "observation time predates feedback connection closure"
        )
    if now - completed > maximum_age:
        raise ObservedPlannerStartStateError("T=1051 feedback is already stale")

    feedback = parse_feedback_line(receipt.response_bytes)
    raw_values = tuple(getattr(feedback, name) for name in _FEEDBACK_ATTRIBUTES)
    if any(value is None for value in raw_values):
        missing = [
            field for field, value in zip(FEEDBACK_FIELDS, raw_values, strict=True)
            if value is None
        ]
        raise ObservedPlannerStartStateError(
            "T=1051 feedback lacks complete planner joints: " + ",".join(missing)
        )
    controller = {
        field: float(value)
        for field, value in zip(FEEDBACK_FIELDS, raw_values, strict=True)
    }
    model: dict[str, float] = {}
    for index, reference_name in enumerate(REFERENCE_JOINT_ORDER):
        projected = (
            snapshot.joint_signs[index] * controller[FEEDBACK_FIELDS[index]]
            + snapshot.joint_zero_offsets_rad[index]
        )
        if not math.isfinite(projected):
            raise ObservedPlannerStartStateError(
                f"projected {reference_name} is not finite"
            )
        if not snapshot.joint_lower_rad[index] <= projected <= snapshot.joint_upper_rad[index]:
            raise ObservedPlannerStartStateError(
                f"projected {reference_name} leaves calibrated bounds"
            )
        model[reference_name] = projected

    return ObservedPlannerStartState(
        run_id=receipt.run_id,
        arm_identity_sha256=receipt.arm_identity_sha256,
        controller_session_id=receipt.controller_session_id,
        request_context_sha256=receipt.request_context_sha256,
        feedback_receipt_sha256=receipt.receipt_sha256,
        calibration_snapshot_sha256=snapshot.snapshot_sha256,
        manifest_id=snapshot.manifest_id,
        active_build_id=snapshot.active_build_id,
        response_completed_monotonic_ns=completed,
        available_monotonic_ns=available,
        valid_until_monotonic_ns=completed + maximum_age,
        controller_joint_positions_rad=controller,
        model_joint_positions_rad=model,
    )


__all__ = [
    "SCHEMA",
    "ObservedPlannerStartState",
    "ObservedPlannerStartStateError",
    "build_observed_planner_start_state",
]
