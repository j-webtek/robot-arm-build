from __future__ import annotations

from pathlib import Path

import pytest

from rocell.application.context import load_simulation_context
from rocell.application.measured_target_reprojection import reproject_measured_target
from rocell.application.measured_trajectory_screening import (
    MeasuredTrajectoryScreeningError,
    screen_measured_trajectory,
)
from rocell.application.observed_planner_start_state import ObservedPlannerStartState
from rocell.calibration import PlannerCalibrationSnapshot, required_planner_artifact_ids
from rocell.geometry import RigidTransform, Rotation3, Vec3
from rocell.kinematics import ARM_JOINT_NAMES
from rocell.models import ModelMotionProposal


WORKSPACE = Path(__file__).resolve().parents[3]
MANIFEST = WORKSPACE / "software/config/system_manifest.json"


@pytest.fixture(scope="module")
def context():
    return load_simulation_context(WORKSPACE, MANIFEST)


def proposal() -> ModelMotionProposal:
    return ModelMotionProposal.from_mapping(
        {
            "schema": "rocell.model_motion_proposal.v1",
            "proposal_id": "keyboard-h-hover-screen-001",
            "device": "keyboard",
            "target_id": "H",
            "coordinate_frame": "keyboard_local",
            "target_mm": {"x": 131.55, "y": 69.0, "z": 0.0},
            "interaction": "HOVER",
            "approach_clearance_mm": 25.0,
            "speed_class": "SLOW",
            "confidence": 0.99,
            "source": {
                "model_id": "test-model",
                "frame_id": "frame-1",
                "image_sha256": "b" * 64,
            },
        }
    )


def snapshot(context) -> PlannerCalibrationSnapshot:
    scenario = context.scenario
    bounds = [
        scenario.controller_joint_intersection_rad[name] for name in ARM_JOINT_NAMES
    ]
    gripper = scenario.controller_gripper_intersection_rad
    board_T_world = scenario.board_T_world
    return PlannerCalibrationSnapshot(
        device="keyboard",
        manifest_id=context.snapshot.manifest_id,
        active_build_id=context.snapshot.active_build_id,
        artifact_hashes={
            item: "a" * 64 for item in required_planner_artifact_ids("keyboard")
        },
        board_T_vendor_world=RigidTransform(
            "B",
            "Wv",
            board_T_world.rotation,
            board_T_world.translation_mm,
        ),
        board_T_device=RigidTransform(
            "B", "keyboard", Rotation3.identity(), Vec3(85.0, 85.0, 21.0)
        ),
        hand_T_tool=RigidTransform(
            "G",
            "T",
            Rotation3.identity(),
            Vec3(0.0, 0.0, scenario.hand_tcp_to_tip_z_mm),
        ),
        robot_reference_identity={
            "arm_identity_hash": "1" * 64,
            "controller_identity_hash": "2" * 64,
            "firmware_identity_hash": "3" * 64,
        },
        joint_zero_offsets_rad=(0.0,) * 6,
        joint_lower_rad=tuple(pair[0] for pair in bounds) + (gripper[0],),
        joint_upper_rad=tuple(pair[1] for pair in bounds) + (gripper[1],),
        joint_signs=(1,) * 6,
        controller_correlation={"model": "test"},
        target_map_sha256=context.targets.content_sha256,
    )


def inputs(context):
    request = proposal()
    measured = snapshot(context)
    reprojection = reproject_measured_target(
        request,
        context.targets,
        measured,
        model_motion_candidate_sha256="c" * 64,
    )
    return request, measured, reprojection


def observed_state(measured: PlannerCalibrationSnapshot, values) -> ObservedPlannerStartState:
    model = dict(
        zip(
            ("b_base", "s_shoulder", "e_elbow", "t_wrist_pitch", "r_wrist_roll"),
            (values[name] for name in ARM_JOINT_NAMES),
            strict=True,
        )
    )
    model["g_gripper"] = 0.0
    return ObservedPlannerStartState(
        run_id="test-run",
        arm_identity_sha256="1" * 64,
        controller_session_id="test-session",
        request_context_sha256="4" * 64,
        feedback_receipt_sha256="5" * 64,
        calibration_snapshot_sha256=measured.snapshot_sha256,
        manifest_id=measured.manifest_id,
        active_build_id=measured.active_build_id,
        response_completed_monotonic_ns=100,
        available_monotonic_ns=101,
        valid_until_monotonic_ns=200,
        controller_joint_positions_rad={key: 0.0 for key in ("b", "s", "e", "t", "r", "g")},
        model_joint_positions_rad=model,
    )


def test_without_observed_start_fails_closed_before_ik(context) -> None:
    request, measured, reprojection = inputs(context)
    report = screen_measured_trajectory(request, context, measured, reprojection)
    assert report["status"] == "BLOCKED_OBSERVED_START_STATE_REQUIRED"
    assert "FRESH_OBSERVED_START_JOINT_STATE_REQUIRED" in report["blockers"]
    assert "FULL_COLLISION_GEOMETRY_INCOMPLETE" in report["blockers"]
    assert report["ik_executed"] is False
    assert report["full_collision_screen_executed"] is False
    assert report["controller_commands"] == []
    assert report["hardware_commands_generated"] == 0
    assert report["physical_authority"] is False


def test_observed_start_runs_bounded_deterministic_ik(context) -> None:
    request, measured, reprojection = inputs(context)
    observed_values = {
        name: context.scenario.ready_arm_joint_positions_rad[name].value
        for name in ARM_JOINT_NAMES
    }
    observed = observed_state(measured, observed_values)
    first = screen_measured_trajectory(
        request,
        context,
        measured,
        reprojection,
        observed_start_state=observed,
        evaluation_monotonic_ns=150,
    )
    second = screen_measured_trajectory(
        request,
        context,
        measured,
        reprojection,
        observed_start_state=observed,
        evaluation_monotonic_ns=150,
    )
    assert first == second
    assert first["ik_executed"] is True
    assert first["waypoints"]
    assert first["joint_results"]
    assert first["status"] in {
        "BLOCKED_DETERMINISTIC_IK_OR_CONTINUITY",
        "BLOCKED_FULL_ROUTE_COLLISION_SCREENING_REQUIRED",
    }
    assert first["full_collision_screen_executed"] is False
    assert first["physical_authority"] is False


def test_rejects_tampered_reprojection_and_start_shape(context) -> None:
    request, measured, reprojection = inputs(context)
    tampered = dict(reprojection)
    tampered["target_id"] = "J"
    with pytest.raises(MeasuredTrajectoryScreeningError, match="hash"):
        screen_measured_trajectory(request, context, measured, tampered)
    with pytest.raises(MeasuredTrajectoryScreeningError, match="authenticated"):
        screen_measured_trajectory(
            request,
            context,
            measured,
            reprojection,
            observed_start_state={"bad": 0.0},  # type: ignore[arg-type]
            evaluation_monotonic_ns=150,
        )
