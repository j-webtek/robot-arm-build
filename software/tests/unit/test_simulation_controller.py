from __future__ import annotations

import math

import pytest

from rocell.simulation import (
    ControllerJointState,
    ControllerPose,
    ControllerSimulationError,
    controller_forward_kinematics,
    controller_raw_to_model_gripper,
    model_gripper_to_controller_raw,
    simulate_t104_trace,
    validate_provisional_simulation_intersection,
)


def _pose(x: float, *, gripper: float = 2.0) -> ControllerPose:
    return ControllerPose(x, 0.0, 100.0, 0.0, 0.0, gripper)


def test_controller_fk_home_matches_audited_firmware_model() -> None:
    state = ControllerJointState(0.0, 0.0, math.pi / 2.0, 0.0, 0.0, math.pi)
    result = controller_forward_kinematics(state)

    assert result.frame == "R_ctrl"
    assert result.x_mm == pytest.approx(346.16, abs=0.02)
    assert result.y_mm == pytest.approx(0.0, abs=1e-9)
    assert result.z_mm == pytest.approx(223.13, abs=0.02)
    assert result.pitch_rad == pytest.approx(0.0)


def test_gripper_model_raw_mapping_is_explicit_and_reversible() -> None:
    closed_raw = model_gripper_to_controller_raw(0.0)
    open_raw = model_gripper_to_controller_raw(1.5)

    assert closed_raw == pytest.approx(math.pi)
    assert open_raw == pytest.approx(math.pi - 1.5)
    assert open_raw < closed_raw
    assert controller_raw_to_model_gripper(closed_raw) == pytest.approx(0.0)
    assert controller_raw_to_model_gripper(open_raw) == pytest.approx(1.5)
    with pytest.raises(ControllerSimulationError):
        model_gripper_to_controller_raw(1.5001)


def test_provisional_joint_intersection_is_a_rejection_check_only() -> None:
    accepted = ControllerJointState(0.0, 0.0, 2.95, 0.0, 0.0, math.pi)
    assert validate_provisional_simulation_intersection(accepted) is accepted

    urdf_only_elbow = ControllerJointState(0.0, 0.0, -0.1, 0.0, 0.0, math.pi)
    with pytest.raises(ControllerSimulationError, match="provisional simulation"):
        validate_provisional_simulation_intersection(urdf_only_elbow)


def test_t104_trace_is_deterministic_cosine_eased_and_never_authoritative() -> None:
    start = _pose(0.0, gripper=math.pi)
    target = _pose(10.0, gripper=math.pi - 1.5)

    first = simulate_t104_trace(start, target, spd_coefficient=2.5)
    second = simulate_t104_trace(start, target, spd_coefficient=2.5)

    assert first == second
    assert len(first.samples) == 5
    assert first.samples[0].interpolation_parameter == pytest.approx(0.0)
    assert first.samples[0].pose.x_mm == pytest.approx(0.0)
    assert first.samples[1].interpolation_parameter == pytest.approx(0.25)
    assert first.samples[1].cosine_eased_fraction == pytest.approx(
        (1.0 - math.cos(math.pi * 0.25)) / 2.0
    )
    assert first.samples[-1].pose.x_mm == pytest.approx(10.0)
    assert all(
        sample.pose.gripper_raw_rad == pytest.approx(target.gripper_raw_rad)
        for sample in first.samples
    )
    evidence = first.to_dict()
    assert evidence["simulation_only"] is True
    assert evidence["live_motion_authorized"] is False
    assert evidence["hardware_commands_generated"] == 0
    assert evidence["commands_transmitted"] == 0
    assert evidence["urdf_frame_equivalence_assumed"] is False


def test_t104_rejects_nonpositive_speed_and_bounds_trace_size() -> None:
    with pytest.raises(ControllerSimulationError, match="positive"):
        simulate_t104_trace(_pose(0.0), _pose(1.0), spd_coefficient=0.0)
    with pytest.raises(ControllerSimulationError, match="positive"):
        simulate_t104_trace(_pose(0.0), _pose(1.0), spd_coefficient=-1.0)
    with pytest.raises(ControllerSimulationError, match="maximum_samples"):
        simulate_t104_trace(
            _pose(0.0),
            _pose(100.0),
            spd_coefficient=0.1,
            maximum_samples=10,
        )


def test_t104_zero_cartesian_delta_is_explicit_gripper_only_sample() -> None:
    start = _pose(10.0, gripper=math.pi)
    target = _pose(10.0, gripper=math.pi - 1.5)

    trace = simulate_t104_trace(start, target, spd_coefficient=1.0)

    assert trace.zero_motion_delta
    assert trace.delta_mixed_units == 0.0
    assert len(trace.samples) == 1
    assert trace.samples[0].pose.gripper_raw_rad == pytest.approx(math.pi - 1.5)
