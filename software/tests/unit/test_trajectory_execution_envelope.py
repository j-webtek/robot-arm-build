from __future__ import annotations

from dataclasses import replace
import json

import pytest

from rocell.application.trajectory_execution_envelope import (
    JointTrajectoryLimits,
    TimedJointWaypoint,
    TrajectoryExecutionEnvelope,
    TrajectoryExecutionEnvelopeError,
    TrajectorySettlePolicy,
    decode_trajectory_execution_envelope_json,
)
from rocell.kinematics import ARM_JOINT_NAMES


def _joints(value: float) -> dict[str, float]:
    return {name: value for name in ARM_JOINT_NAMES}


def _limits(
    *, velocity: float = 1.0, acceleration: float = 5.0, jerk: float = 20.0
) -> JointTrajectoryLimits:
    return JointTrajectoryLimits(
        lower_position_rad=_joints(-2.0),
        upper_position_rad=_joints(2.0),
        maximum_velocity_rad_s=_joints(velocity),
        maximum_acceleration_rad_s2=_joints(acceleration),
        maximum_jerk_rad_s3=_joints(jerk),
    )


def _waypoints() -> tuple[TimedJointWaypoint, ...]:
    return tuple(
        TimedJointWaypoint(index, index * 1_000_000_000, _joints(index * 0.1))
        for index in range(4)
    )


def _envelope(**changes) -> TrajectoryExecutionEnvelope:
    values = {
        "correlation_id": "batch-1-action-0-attempt-1",
        "batch_sha256": "a" * 64,
        "action_index": 0,
        "proposal_sha256": "b" * 64,
        "planner_gate_sha256": "c" * 64,
        "trajectory_screening_sha256": "d" * 64,
        "collision_screening_sha256": "e" * 64,
        "observed_start_state_sha256": "f" * 64,
        "observed_start_joint_positions_rad": _joints(0.0),
        "build_snapshot_sha256": "1" * 64,
        "calibration_snapshot_sha256": "2" * 64,
        "configuration_epoch_sha256": "3" * 64,
        "controller_session_id": "controller-session-1",
        "issued_monotonic_ns": 10_000_000_000,
        "deadline_monotonic_ns": 20_000_000_000,
        "limits": _limits(),
        "settle_policy": TrajectorySettlePolicy(
            position_tolerance_rad=_joints(0.01),
            velocity_tolerance_rad_s=_joints(0.02),
            dwell_ns=100_000_000,
        ),
        "waypoints": _waypoints(),
    }
    values.update(changes)
    return TrajectoryExecutionEnvelope(**values)


def test_envelope_round_trip_is_sealed_and_controller_independent() -> None:
    envelope = _envelope()
    encoded = json.dumps(envelope.to_dict(), sort_keys=True).encode("utf-8")
    decoded = decode_trajectory_execution_envelope_json(encoded)

    assert decoded == envelope
    assert decoded.envelope_sha256 == envelope.envelope_sha256
    assert decoded.to_dict()["wire_commands"] == []
    assert decoded.to_dict()["hardware_access"] is False
    assert decoded.to_dict()["physical_authority"] is False
    assert tuple(decoded.waypoints[0].joint_positions_rad) == ARM_JOINT_NAMES


def test_envelope_rejects_hash_tamper_and_duplicate_json_field() -> None:
    document = _envelope().to_dict()
    document["deadline_monotonic_ns"] += 1
    with pytest.raises(TrajectoryExecutionEnvelopeError, match="content hash"):
        TrajectoryExecutionEnvelope.from_mapping(document)

    encoded = json.dumps(_envelope().to_dict(), separators=(",", ":"))
    duplicate = encoded.replace(
        '"correlation_id":"batch-1-action-0-attempt-1"',
        '"correlation_id":"batch-1-action-0-attempt-1","correlation_id":"other"',
        1,
    )
    with pytest.raises(TrajectoryExecutionEnvelopeError, match="duplicate JSON"):
        decode_trajectory_execution_envelope_json(duplicate.encode("utf-8"))


def test_envelope_rejects_nonmonotonic_timing_and_deadline_overrun() -> None:
    bad_timing = list(_waypoints())
    bad_timing[2] = replace(bad_timing[2], time_from_start_ns=1_000_000_000)
    with pytest.raises(TrajectoryExecutionEnvelopeError, match="timing"):
        _envelope(waypoints=tuple(bad_timing))

    with pytest.raises(TrajectoryExecutionEnvelopeError, match="deadline"):
        _envelope(deadline_monotonic_ns=12_000_000_000)


def test_envelope_rejects_position_velocity_acceleration_and_jerk_limits() -> None:
    outside = list(_waypoints())
    outside[-1] = replace(outside[-1], joint_positions_rad=_joints(2.1))
    with pytest.raises(TrajectoryExecutionEnvelopeError, match="position limits"):
        _envelope(waypoints=tuple(outside))

    fast = list(_waypoints())
    fast[1] = replace(
        fast[1], time_from_start_ns=100_000_000, joint_positions_rad=_joints(0.5)
    )
    with pytest.raises(TrajectoryExecutionEnvelopeError, match="velocity"):
        _envelope(waypoints=tuple(fast))

    accelerating = (
        TimedJointWaypoint(0, 0, _joints(0.0)),
        TimedJointWaypoint(1, 1_000_000_000, _joints(0.1)),
        TimedJointWaypoint(2, 2_000_000_000, _joints(0.3)),
        TimedJointWaypoint(3, 3_000_000_000, _joints(0.6)),
    )
    with pytest.raises(TrajectoryExecutionEnvelopeError, match="acceleration"):
        _envelope(waypoints=accelerating, limits=_limits(acceleration=0.01))

    jerky = (
        TimedJointWaypoint(0, 0, _joints(0.0)),
        TimedJointWaypoint(1, 1_000_000_000, _joints(0.1)),
        TimedJointWaypoint(2, 2_000_000_000, _joints(0.2)),
        TimedJointWaypoint(3, 3_000_000_000, _joints(0.4)),
    )
    with pytest.raises(TrajectoryExecutionEnvelopeError, match="jerk"):
        _envelope(waypoints=jerky, limits=_limits(jerk=0.01))


def test_envelope_requires_collision_proof_and_exact_joint_set() -> None:
    with pytest.raises(TrajectoryExecutionEnvelopeError, match="collision"):
        _envelope(continuous_collision_proven=False)

    incomplete = _joints(0.0)
    incomplete.pop(ARM_JOINT_NAMES[-1])
    with pytest.raises(TrajectoryExecutionEnvelopeError, match="five ordered"):
        TimedJointWaypoint(0, 0, incomplete)

    with pytest.raises(TrajectoryExecutionEnvelopeError, match="observed start"):
        _envelope(observed_start_joint_positions_rad=_joints(0.1))
