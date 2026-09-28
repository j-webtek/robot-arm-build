from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

import pytest

from rocell.application._pinned_model import load_pinned_urdf
from rocell.application.context import load_simulation_context
from rocell.application.typing_execution_plan_v1 import (
    TypingExecutionConfigV1,
    compile_typing_execution_plan_v1,
)
from rocell.application.typing_trajectory_ik_screen_v1 import (
    READY_STATUS,
    TypingTrajectoryIkScreenV1Error,
    TypingTrajectoryIkSeedV1,
    screen_typing_trajectory_ik_v1,
)
from rocell.application.typing_trajectory_plan_v1 import (
    TypingTrajectoryPolicyV1,
    compile_typing_trajectory_plan_v1,
)
from rocell.calibration import PlannerCalibrationSnapshot, required_planner_artifact_ids
from rocell.geometry import JointPosition, Point3Mm as GeometryPoint3Mm, RigidTransform, Rotation3, Vec3
from rocell.kinematics import ARM_JOINT_NAMES, BoardToolTipTarget, IkOptions, RoArmM3NumericalIk
from rocell.models import (
    Interaction,
    ModelMotionBatchV2,
    ModelMotionProposalV2,
    MotionCapabilityV2,
    MotionEvidenceV2,
    MotionGeometryV2,
    MotionUncertaintyV2,
    Point3Mm,
    ProposalDevice,
    SpeedClass,
    UncertaintyBoundType,
)


WORKSPACE = Path(__file__).resolve().parents[3]
MANIFEST = WORKSPACE / "software/config/system_manifest.json"


def _canonical(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
    ).encode("utf-8")


@pytest.fixture(scope="module")
def context():
    return load_simulation_context(WORKSPACE, MANIFEST)


def _snapshot(context) -> PlannerCalibrationSnapshot:
    scenario = context.scenario
    bounds = [scenario.controller_joint_intersection_rad[name] for name in ARM_JOINT_NAMES]
    gripper = scenario.controller_gripper_intersection_rad
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
            scenario.board_T_world.rotation,
            scenario.board_T_world.translation_mm,
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
        controller_correlation={"model": "synthetic-offline-test"},
        target_map_sha256=context.targets.content_sha256,
    )


def _ready_joint_values(context) -> dict[str, float]:
    return {
        name: context.scenario.ready_arm_joint_positions_rad[name].value
        for name in ARM_JOINT_NAMES
    }


def _ready_tip(context, snapshot: PlannerCalibrationSnapshot) -> GeometryPoint3Mm:
    model = load_pinned_urdf(
        context.scenario.model_path, context.scenario.model_sha256
    ).model
    bounds = {
        name: context.scenario.controller_joint_intersection_rad[name]
        for name in ARM_JOINT_NAMES
    }
    solver = RoArmM3NumericalIk(
        model=model,
        board_T_world=RigidTransform(
            "board",
            "world",
            snapshot.board_T_vendor_world.rotation,
            snapshot.board_T_vendor_world.translation_mm,
        ),
        hand_tcp_to_tip_z_mm=snapshot.hand_T_tool.translation_mm.z,
        fixed_gripper_position=context.scenario.fixed_gripper_position,
        ready_arm_joint_positions=context.scenario.ready_arm_joint_positions_rad,
        gripper_bounds_rad=context.scenario.controller_gripper_intersection_rad,
        options=IkOptions(),
        joint_bounds_rad=bounds,
    )
    return solver.evaluate(
        BoardToolTipTarget(GeometryPoint3Mm("board", 0.0, 0.0, 0.0)),
        {
            name: JointPosition.radians(value)
            for name, value in _ready_joint_values(context).items()
        },
    ).tip_position_board_mm


def _trajectory(context, snapshot: PlannerCalibrationSnapshot):
    tip = _ready_tip(context, snapshot)
    contact = Point3Mm("board", tip.x, tip.y, tip.z - 5.0)
    proposal = ModelMotionProposalV2(
        proposal_id="proposal-ready-local",
        action_index=0,
        device=ProposalDevice.KEYBOARD,
        target_id="H",
        target=contact,
        interaction=Interaction.CONTACT,
        observation_confidence=0.99,
    )
    batch = ModelMotionBatchV2(
        batch_id="batch-ready-local",
        request_id="request-ready-local",
        intent_plan_sha256="1" * 64,
        device=ProposalDevice.KEYBOARD,
        capability=MotionCapabilityV2("keyboard-dev", "2" * 64),
        geometry=MotionGeometryV2(
            coordinate_profile="board_mm_xy_plane_v2",
            coordinate_units="mm",
            board_frame_definition_sha256="3" * 64,
            placement_observation_sha256="4" * 64,
            target_catalog_sha256="5" * 64,
        ),
        evidence=MotionEvidenceV2(
            capture_id="capture",
            frame_id="frame",
            image_sha256="6" * 64,
            camera_identity_sha256="7" * 64,
            capture_clock_domain_id="clock",
            model_id="model",
            model_sha256="8" * 64,
            scene_observation_sha256="9" * 64,
            precision_observation_sha256="a" * 64,
            fusion_decision_sha256="b" * 64,
            scene_lease_id="lease",
            scene_lease_issuer_id="issuer",
            scene_lease_sha256="c" * 64,
            captured_at_epoch_ms=1,
            evaluated_at_epoch_ms=2,
            expires_at_epoch_ms=10_000,
        ),
        uncertainty=MotionUncertaintyV2(
            bound_type=UncertaintyBoundType.PLANAR_L2_DISK,
            error_bound_mm=1.0,
            coverage_probability=0.99,
            qualification_sha256="d" * 64,
            evidence_method_sha256="e" * 64,
            domain_id="domain",
            covered_target_ids=("H",),
        ),
        proposals=(proposal,),
    )
    ingress = {
        "schema": "rocell.model_motion_ingress.v2",
        "status": "ACCEPTED_V2_FOR_FRESH_SEQUENTIAL_PLANNER_GATES",
        "batch_sha256": batch.batch_sha256,
        "intent_plan_sha256": batch.intent_plan_sha256,
        "request_id": batch.request_id,
        "ordered_target_ids": ["H"],
        "controller_commands": [],
        "hardware_commands_generated": 0,
        "hardware_access": False,
        "physical_authority": False,
    }
    ingress["ingress_sha256"] = hashlib.sha256(_canonical(ingress)).hexdigest()
    execution = compile_typing_execution_plan_v1(
        batch,
        ingress,
        config=TypingExecutionConfigV1(
            config_id="ready-local-offline",
            calibration_snapshot_sha256=snapshot.snapshot_sha256,
            tool_profile_sha256="0" * 64,
            dynamics_profile_sha256="1" * 64,
            route_reference_point=Point3Mm("board", tip.x, tip.y, tip.z),
            hover_clearance_mm=5.0,
            settle_position_tolerance_mm=0.5,
            settle_velocity_tolerance_mm_s=1.0,
            settle_hold_ms=100,
            preview_horizon=1,
            speed_class=SpeedClass.SLOW,
        ),
    )
    trajectory = compile_typing_trajectory_plan_v1(
        execution,
        policy=TypingTrajectoryPolicyV1(
            policy_id="ready-local-quintic-v1",
            maximum_cartesian_step_mm=1.0,
            maximum_velocity_mm_s=40.0,
            maximum_acceleration_mm_s2=80.0,
            maximum_jerk_mm_s3=400.0,
            hover_settle_ms=100,
            contact_dwell_ms=60,
        ),
    )
    return execution, trajectory


def _seed(context, snapshot: PlannerCalibrationSnapshot) -> TypingTrajectoryIkSeedV1:
    return TypingTrajectoryIkSeedV1(
        seed_id="ready-joint-seed",
        calibration_snapshot_sha256=snapshot.snapshot_sha256,
        build_snapshot_sha256=context.snapshot.snapshot_hash,
        joint_positions_rad=_ready_joint_values(context),
    )


def test_exact_t2a_samples_run_through_canonical_ik_with_zero_authority(context):
    snapshot = _snapshot(context)
    execution, trajectory = _trajectory(context, snapshot)
    first = screen_typing_trajectory_ik_v1(
        execution, trajectory, context, snapshot, _seed(context, snapshot)
    )
    second = screen_typing_trajectory_ik_v1(
        execution, trajectory, context, snapshot, _seed(context, snapshot)
    )

    assert first == second
    assert first["status"] == READY_STATUS
    assert first["ik_screening_executed"] is True
    assert first["ik_all_samples_accepted"] is True
    assert first["evaluated_sample_count"] == first["sample_count"]
    assert first["collision_screening_executed"] is False
    assert first["blockers"] == ["INSTALLED_GEOMETRY_COLLISION_SCREENING_REQUIRED"]
    assert first["controller_commands"] == []
    assert first["hardware_commands_generated"] == 0
    assert first["hardware_access"] is first["physical_authority"] is False


def test_seed_is_identity_bound_and_rejects_nonfinite_or_noncanonical_values(context):
    snapshot = _snapshot(context)
    values = _ready_joint_values(context)
    with pytest.raises(TypingTrajectoryIkScreenV1Error, match="canonical arm-joint set"):
        TypingTrajectoryIkSeedV1(
            "bad-set", snapshot.snapshot_sha256, context.snapshot.snapshot_hash,
            {"wrong": 0.0},
        )
    values[ARM_JOINT_NAMES[0]] = math.inf
    with pytest.raises(TypingTrajectoryIkScreenV1Error, match="must be finite"):
        TypingTrajectoryIkSeedV1(
            "bad-finite", snapshot.snapshot_sha256,
            context.snapshot.snapshot_hash, values,
        )

    good = _seed(context, snapshot)
    crossed = TypingTrajectoryIkSeedV1(
        good.seed_id,
        "f" * 64,
        good.build_snapshot_sha256,
        good.joint_positions_rad,
    )
    with pytest.raises(TypingTrajectoryIkScreenV1Error, match="identities differ"):
        execution, trajectory = _trajectory(context, snapshot)
        screen_typing_trajectory_ik_v1(
            execution, trajectory, context, snapshot, crossed
        )


def test_sample_resource_bound_fails_before_ik(context):
    snapshot = _snapshot(context)
    execution, trajectory = _trajectory(context, snapshot)
    from rocell.application.trajectory_simulation import TrajectorySimulationPolicy

    with pytest.raises(TypingTrajectoryIkScreenV1Error, match="sample count exceeds"):
        screen_typing_trajectory_ik_v1(
            execution,
            trajectory,
            context,
            snapshot,
            _seed(context, snapshot),
            policy=TrajectorySimulationPolicy(
                maximum_cartesian_step_mm=1.0,
                maximum_refinement_rounds=0,
                maximum_waypoints_per_round=8,
                maximum_total_ik_solves=8,
            ),
        )
