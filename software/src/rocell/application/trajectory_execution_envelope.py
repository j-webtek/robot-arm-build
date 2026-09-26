"""Sealed, controller-independent joint trajectory execution envelope.

The envelope is the only planned shape a future writable adapter may accept.
It contains radians and monotonic nanoseconds, never Waveshare JSON, serial
bytes, a port name, or execution authority.  A separate single-use permit is
still required before any physical writer may encode it.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
import re
from types import MappingProxyType
from typing import Any, Mapping, Sequence

from rocell.kinematics import ARM_JOINT_NAMES


SCHEMA = "rocell.trajectory_execution_envelope.v1"
MAX_WAYPOINTS = 512
MAX_PAYLOAD_BYTES = 2 * 1024 * 1024
MAX_DURATION_NS = 120_000_000_000
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")


class TrajectoryExecutionEnvelopeError(ValueError):
    """The proposed execution trajectory is malformed, unsafe, or unbound."""


def _canonical(value: object) -> bytes:
    try:
        return json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise TrajectoryExecutionEnvelopeError("value is not canonical JSON") from exc


def _digest(value: object, label: str) -> str:
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        raise TrajectoryExecutionEnvelopeError(f"{label} must be a SHA-256 digest")
    return value


def _identifier(value: object, label: str) -> str:
    if not isinstance(value, str) or _IDENTIFIER.fullmatch(value) is None:
        raise TrajectoryExecutionEnvelopeError(f"{label} must be a bounded identifier")
    return value


def _positive_int(value: object, label: str, *, allow_zero: bool = False) -> int:
    minimum = 0 if allow_zero else 1
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        qualifier = "nonnegative" if allow_zero else "positive"
        raise TrajectoryExecutionEnvelopeError(f"{label} must be a {qualifier} integer")
    return value


def _number(value: object, label: str, *, positive: bool = False) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TrajectoryExecutionEnvelopeError(f"{label} must be numeric")
    result = float(value)
    if not math.isfinite(result) or (positive and result <= 0.0):
        raise TrajectoryExecutionEnvelopeError(f"{label} must be finite and valid")
    return result


def _joint_map(
    value: Mapping[str, float], label: str, *, positive: bool = False
) -> MappingProxyType:
    if not isinstance(value, Mapping) or set(value) != set(ARM_JOINT_NAMES):
        raise TrajectoryExecutionEnvelopeError(
            f"{label} must contain exactly the five ordered arm joints"
        )
    return MappingProxyType(
        {
            name: _number(value[name], f"{label}.{name}", positive=positive)
            for name in ARM_JOINT_NAMES
        }
    )


@dataclass(frozen=True, slots=True)
class JointTrajectoryLimits:
    lower_position_rad: Mapping[str, float]
    upper_position_rad: Mapping[str, float]
    maximum_velocity_rad_s: Mapping[str, float]
    maximum_acceleration_rad_s2: Mapping[str, float]
    maximum_jerk_rad_s3: Mapping[str, float]

    def __post_init__(self) -> None:
        lower = _joint_map(self.lower_position_rad, "lower_position_rad")
        upper = _joint_map(self.upper_position_rad, "upper_position_rad")
        for name in ARM_JOINT_NAMES:
            if lower[name] >= upper[name]:
                raise TrajectoryExecutionEnvelopeError(
                    f"joint bounds are empty for {name}"
                )
        object.__setattr__(self, "lower_position_rad", lower)
        object.__setattr__(self, "upper_position_rad", upper)
        for field in (
            "maximum_velocity_rad_s",
            "maximum_acceleration_rad_s2",
            "maximum_jerk_rad_s3",
        ):
            object.__setattr__(
                self, field, _joint_map(getattr(self, field), field, positive=True)
            )

    def to_dict(self) -> dict[str, object]:
        return {
            field: dict(getattr(self, field))
            for field in (
                "lower_position_rad",
                "upper_position_rad",
                "maximum_velocity_rad_s",
                "maximum_acceleration_rad_s2",
                "maximum_jerk_rad_s3",
            )
        }

    @classmethod
    def from_mapping(cls, value: object) -> "JointTrajectoryLimits":
        fields = {
            "lower_position_rad", "upper_position_rad",
            "maximum_velocity_rad_s", "maximum_acceleration_rad_s2",
            "maximum_jerk_rad_s3",
        }
        if not isinstance(value, Mapping) or set(value) != fields:
            raise TrajectoryExecutionEnvelopeError("trajectory limit fields are invalid")
        return cls(**{field: value[field] for field in fields})


@dataclass(frozen=True, slots=True)
class TrajectorySettlePolicy:
    position_tolerance_rad: Mapping[str, float]
    velocity_tolerance_rad_s: Mapping[str, float]
    dwell_ns: int

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "position_tolerance_rad",
            _joint_map(self.position_tolerance_rad, "position_tolerance_rad", positive=True),
        )
        object.__setattr__(
            self, "velocity_tolerance_rad_s",
            _joint_map(
                self.velocity_tolerance_rad_s,
                "velocity_tolerance_rad_s",
                positive=True,
            ),
        )
        _positive_int(self.dwell_ns, "dwell_ns")

    def to_dict(self) -> dict[str, object]:
        return {
            "position_tolerance_rad": dict(self.position_tolerance_rad),
            "velocity_tolerance_rad_s": dict(self.velocity_tolerance_rad_s),
            "dwell_ns": self.dwell_ns,
        }

    @classmethod
    def from_mapping(cls, value: object) -> "TrajectorySettlePolicy":
        fields = {"position_tolerance_rad", "velocity_tolerance_rad_s", "dwell_ns"}
        if not isinstance(value, Mapping) or set(value) != fields:
            raise TrajectoryExecutionEnvelopeError("settle policy fields are invalid")
        return cls(
            position_tolerance_rad=value["position_tolerance_rad"],
            velocity_tolerance_rad_s=value["velocity_tolerance_rad_s"],
            dwell_ns=value["dwell_ns"],
        )


@dataclass(frozen=True, slots=True)
class TimedJointWaypoint:
    sequence: int
    time_from_start_ns: int
    joint_positions_rad: Mapping[str, float]

    def __post_init__(self) -> None:
        _positive_int(self.sequence, "waypoint sequence", allow_zero=True)
        _positive_int(self.time_from_start_ns, "time_from_start_ns", allow_zero=True)
        object.__setattr__(
            self, "joint_positions_rad",
            _joint_map(self.joint_positions_rad, "joint_positions_rad"),
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "sequence": self.sequence,
            "time_from_start_ns": self.time_from_start_ns,
            "joint_positions_rad": dict(self.joint_positions_rad),
        }

    @classmethod
    def from_mapping(cls, value: object) -> "TimedJointWaypoint":
        fields = {"sequence", "time_from_start_ns", "joint_positions_rad"}
        if not isinstance(value, Mapping) or set(value) != fields:
            raise TrajectoryExecutionEnvelopeError("waypoint fields are invalid")
        return cls(
            sequence=value["sequence"],
            time_from_start_ns=value["time_from_start_ns"],
            joint_positions_rad=value["joint_positions_rad"],
        )


def _validate_dynamics(
    waypoints: tuple[TimedJointWaypoint, ...], limits: JointTrajectoryLimits
) -> None:
    velocities: list[dict[str, float]] = []
    durations: list[float] = []
    for left, right in zip(waypoints, waypoints[1:], strict=False):
        duration = (right.time_from_start_ns - left.time_from_start_ns) / 1e9
        durations.append(duration)
        velocity = {
            name: (right.joint_positions_rad[name] - left.joint_positions_rad[name])
            / duration
            for name in ARM_JOINT_NAMES
        }
        for name, value in velocity.items():
            if abs(value) > limits.maximum_velocity_rad_s[name] + 1e-12:
                raise TrajectoryExecutionEnvelopeError(
                    f"segment velocity exceeds the limit for {name}"
                )
        velocities.append(velocity)

    accelerations: list[dict[str, float]] = []
    acceleration_intervals: list[float] = []
    for index in range(1, len(velocities)):
        interval = (durations[index - 1] + durations[index]) / 2.0
        acceleration_intervals.append(interval)
        acceleration = {
            name: (velocities[index][name] - velocities[index - 1][name]) / interval
            for name in ARM_JOINT_NAMES
        }
        for name, value in acceleration.items():
            if abs(value) > limits.maximum_acceleration_rad_s2[name] + 1e-12:
                raise TrajectoryExecutionEnvelopeError(
                    f"segment acceleration exceeds the limit for {name}"
                )
        accelerations.append(acceleration)

    for index in range(1, len(accelerations)):
        interval = (
            acceleration_intervals[index - 1] + acceleration_intervals[index]
        ) / 2.0
        for name in ARM_JOINT_NAMES:
            jerk = (
                accelerations[index][name] - accelerations[index - 1][name]
            ) / interval
            if abs(jerk) > limits.maximum_jerk_rad_s3[name] + 1e-12:
                raise TrajectoryExecutionEnvelopeError(
                    f"segment jerk exceeds the limit for {name}"
                )


@dataclass(frozen=True, slots=True)
class TrajectoryExecutionEnvelope:
    correlation_id: str
    batch_sha256: str
    action_index: int
    proposal_sha256: str
    planner_gate_sha256: str
    trajectory_screening_sha256: str
    collision_screening_sha256: str
    observed_start_state_sha256: str
    observed_start_joint_positions_rad: Mapping[str, float]
    build_snapshot_sha256: str
    calibration_snapshot_sha256: str
    configuration_epoch_sha256: str
    controller_session_id: str
    issued_monotonic_ns: int
    deadline_monotonic_ns: int
    limits: JointTrajectoryLimits
    settle_policy: TrajectorySettlePolicy
    waypoints: tuple[TimedJointWaypoint, ...]
    continuous_collision_proven: bool = True
    schema: str = SCHEMA

    def __post_init__(self) -> None:
        if self.schema != SCHEMA:
            raise TrajectoryExecutionEnvelopeError("unsupported envelope schema")
        _identifier(self.correlation_id, "correlation_id")
        _identifier(self.controller_session_id, "controller_session_id")
        for field in (
            "batch_sha256", "proposal_sha256", "planner_gate_sha256",
            "trajectory_screening_sha256", "collision_screening_sha256",
            "observed_start_state_sha256", "build_snapshot_sha256",
            "calibration_snapshot_sha256", "configuration_epoch_sha256",
        ):
            _digest(getattr(self, field), field)
        _positive_int(self.action_index, "action_index", allow_zero=True)
        issued = _positive_int(self.issued_monotonic_ns, "issued_monotonic_ns")
        deadline = _positive_int(self.deadline_monotonic_ns, "deadline_monotonic_ns")
        if deadline <= issued:
            raise TrajectoryExecutionEnvelopeError("deadline must follow issuance")
        if not isinstance(self.limits, JointTrajectoryLimits):
            raise TypeError("limits must be JointTrajectoryLimits")
        if not isinstance(self.settle_policy, TrajectorySettlePolicy):
            raise TypeError("settle_policy must be TrajectorySettlePolicy")
        observed_start = _joint_map(
            self.observed_start_joint_positions_rad,
            "observed_start_joint_positions_rad",
        )
        object.__setattr__(
            self, "observed_start_joint_positions_rad", observed_start
        )
        if self.continuous_collision_proven is not True:
            raise TrajectoryExecutionEnvelopeError(
                "continuous collision screening must be proven"
            )
        waypoints = tuple(self.waypoints)
        if not 2 <= len(waypoints) <= MAX_WAYPOINTS:
            raise TrajectoryExecutionEnvelopeError("waypoint count is outside bounds")
        if any(not isinstance(item, TimedJointWaypoint) for item in waypoints):
            raise TypeError("waypoints must contain TimedJointWaypoint values")
        if [item.sequence for item in waypoints] != list(range(len(waypoints))):
            raise TrajectoryExecutionEnvelopeError("waypoint sequence is not contiguous")
        if waypoints[0].time_from_start_ns != 0 or any(
            right.time_from_start_ns <= left.time_from_start_ns
            for left, right in zip(waypoints, waypoints[1:], strict=False)
        ):
            raise TrajectoryExecutionEnvelopeError("waypoint timing is not monotonic")
        duration = waypoints[-1].time_from_start_ns
        if duration > MAX_DURATION_NS or issued + duration > deadline:
            raise TrajectoryExecutionEnvelopeError("trajectory exceeds its deadline")
        for waypoint in waypoints:
            for name in ARM_JOINT_NAMES:
                value = waypoint.joint_positions_rad[name]
                if not (
                    self.limits.lower_position_rad[name]
                    <= value
                    <= self.limits.upper_position_rad[name]
                ):
                    raise TrajectoryExecutionEnvelopeError(
                        f"waypoint leaves position limits for {name}"
                    )
        for name in ARM_JOINT_NAMES:
            if abs(waypoints[0].joint_positions_rad[name] - observed_start[name]) > 1e-12:
                raise TrajectoryExecutionEnvelopeError(
                    f"first waypoint differs from observed start for {name}"
                )
            joint_range = (
                self.limits.upper_position_rad[name]
                - self.limits.lower_position_rad[name]
            )
            if self.settle_policy.position_tolerance_rad[name] >= joint_range:
                raise TrajectoryExecutionEnvelopeError(
                    f"settle position tolerance is unbounded for {name}"
                )
            if (
                self.settle_policy.velocity_tolerance_rad_s[name]
                > self.limits.maximum_velocity_rad_s[name]
            ):
                raise TrajectoryExecutionEnvelopeError(
                    f"settle velocity tolerance exceeds the limit for {name}"
                )
        _validate_dynamics(waypoints, self.limits)
        object.__setattr__(self, "waypoints", waypoints)

    def unsigned_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "correlation_id": self.correlation_id,
            "batch_sha256": self.batch_sha256,
            "action_index": self.action_index,
            "proposal_sha256": self.proposal_sha256,
            "planner_gate_sha256": self.planner_gate_sha256,
            "trajectory_screening_sha256": self.trajectory_screening_sha256,
            "collision_screening_sha256": self.collision_screening_sha256,
            "observed_start_state_sha256": self.observed_start_state_sha256,
            "observed_start_joint_positions_rad": dict(
                self.observed_start_joint_positions_rad
            ),
            "build_snapshot_sha256": self.build_snapshot_sha256,
            "calibration_snapshot_sha256": self.calibration_snapshot_sha256,
            "configuration_epoch_sha256": self.configuration_epoch_sha256,
            "controller_session_id": self.controller_session_id,
            "issued_monotonic_ns": self.issued_monotonic_ns,
            "deadline_monotonic_ns": self.deadline_monotonic_ns,
            "limits": self.limits.to_dict(),
            "settle_policy": self.settle_policy.to_dict(),
            "waypoints": [item.to_dict() for item in self.waypoints],
            "continuous_collision_proven": self.continuous_collision_proven,
            "wire_commands": [],
            "hardware_access": False,
            "physical_authority": False,
        }

    @property
    def envelope_sha256(self) -> str:
        return hashlib.sha256(_canonical(self.unsigned_dict())).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        return {**self.unsigned_dict(), "envelope_sha256": self.envelope_sha256}

    @classmethod
    def from_mapping(cls, value: object) -> "TrajectoryExecutionEnvelope":
        fields = {
            "schema", "correlation_id", "batch_sha256", "action_index",
            "proposal_sha256", "planner_gate_sha256",
            "trajectory_screening_sha256", "collision_screening_sha256",
            "observed_start_state_sha256", "observed_start_joint_positions_rad",
            "build_snapshot_sha256",
            "calibration_snapshot_sha256", "configuration_epoch_sha256",
            "controller_session_id", "issued_monotonic_ns",
            "deadline_monotonic_ns", "limits", "settle_policy", "waypoints",
            "continuous_collision_proven", "wire_commands", "hardware_access",
            "physical_authority", "envelope_sha256",
        }
        if not isinstance(value, Mapping) or set(value) != fields:
            raise TrajectoryExecutionEnvelopeError("envelope fields are invalid")
        if (
            value["wire_commands"] != []
            or value["hardware_access"] is not False
            or value["physical_authority"] is not False
        ):
            raise TrajectoryExecutionEnvelopeError("envelope violates zero authority")
        raw_waypoints = value["waypoints"]
        if not isinstance(raw_waypoints, Sequence) or isinstance(
            raw_waypoints, (str, bytes)
        ):
            raise TrajectoryExecutionEnvelopeError("waypoints must be an array")
        envelope = cls(
            **{
                field: value[field]
                for field in fields
                if field not in {
                    "limits", "settle_policy", "waypoints", "wire_commands",
                    "hardware_access", "physical_authority", "envelope_sha256",
                }
            },
            limits=JointTrajectoryLimits.from_mapping(value["limits"]),
            settle_policy=TrajectorySettlePolicy.from_mapping(value["settle_policy"]),
            waypoints=tuple(TimedJointWaypoint.from_mapping(item) for item in raw_waypoints),
        )
        claimed = _digest(value["envelope_sha256"], "envelope_sha256")
        if claimed != envelope.envelope_sha256:
            raise TrajectoryExecutionEnvelopeError("envelope content hash is invalid")
        return envelope


def decode_trajectory_execution_envelope_json(
    payload: bytes,
) -> TrajectoryExecutionEnvelope:
    if not isinstance(payload, bytes):
        raise TypeError("payload must be bytes")
    if not payload or len(payload) > MAX_PAYLOAD_BYTES:
        raise TrajectoryExecutionEnvelopeError("payload is empty or oversized")

    def unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, item in pairs:
            if key in result:
                raise TrajectoryExecutionEnvelopeError(f"duplicate JSON field {key!r}")
            result[key] = item
        return result

    try:
        value = json.loads(
            payload.decode("utf-8"), object_pairs_hook=unique,
            parse_constant=lambda item: (_ for _ in ()).throw(
                TrajectoryExecutionEnvelopeError(
                    f"non-finite JSON constant {item!r}"
                )
            ),
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise TrajectoryExecutionEnvelopeError("payload is not strict UTF-8 JSON") from exc
    return TrajectoryExecutionEnvelope.from_mapping(value)


__all__ = [
    "MAX_DURATION_NS", "MAX_PAYLOAD_BYTES", "MAX_WAYPOINTS", "SCHEMA",
    "JointTrajectoryLimits", "TimedJointWaypoint", "TrajectoryExecutionEnvelope",
    "TrajectoryExecutionEnvelopeError", "TrajectorySettlePolicy",
    "decode_trajectory_execution_envelope_json",
]
