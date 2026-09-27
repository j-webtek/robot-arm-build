from __future__ import annotations

import hashlib
import json
import math

import pytest

from rocell.application.typing_execution_plan_v1 import (
    TypingExecutionConfigV1,
    compile_typing_execution_plan_v1,
)
from rocell.application.typing_trajectory_plan_v1 import (
    STATUS,
    TimingConstraintV1,
    TypingTrajectoryPlanV1Error,
    TypingTrajectoryPolicyV1,
    compile_typing_trajectory_plan_v1,
)
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
from rocell.motion.primitives import MotionPhase


def _canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False).encode()


def _execution_plan(targets=("H", "H", "1", "PERIOD")):
    positions = {"H": (12.0, 15.0), "1": (-28.0, -5.0), "PERIOD": (34.0, 28.0)}
    proposals = tuple(ModelMotionProposalV2(
        proposal_id=f"proposal-{index}", action_index=index,
        device=ProposalDevice.KEYBOARD, target_id=target,
        target=Point3Mm("board", *positions[target], 2.0),
        interaction=Interaction.CONTACT, observation_confidence=0.99,
    ) for index, target in enumerate(targets))
    batch = ModelMotionBatchV2(
        batch_id="batch-timing", request_id="request-timing",
        intent_plan_sha256="1" * 64, device=ProposalDevice.KEYBOARD,
        capability=MotionCapabilityV2("keyboard-dev", "2" * 64),
        geometry=MotionGeometryV2(
            coordinate_profile="board_mm_xy_plane_v2", coordinate_units="mm",
            board_frame_definition_sha256="3" * 64,
            placement_observation_sha256="4" * 64,
            target_catalog_sha256="5" * 64),
        evidence=MotionEvidenceV2(
            capture_id="capture", frame_id="frame", image_sha256="6" * 64,
            camera_identity_sha256="7" * 64, capture_clock_domain_id="clock",
            model_id="model", model_sha256="8" * 64,
            scene_observation_sha256="9" * 64,
            precision_observation_sha256="a" * 64,
            fusion_decision_sha256="b" * 64, scene_lease_id="lease",
            scene_lease_issuer_id="issuer", scene_lease_sha256="c" * 64,
            captured_at_epoch_ms=1, evaluated_at_epoch_ms=2,
            expires_at_epoch_ms=10_000),
        uncertainty=MotionUncertaintyV2(
            bound_type=UncertaintyBoundType.PLANAR_L2_DISK,
            error_bound_mm=1.0, coverage_probability=0.99,
            qualification_sha256="d" * 64, evidence_method_sha256="e" * 64,
            domain_id="domain", covered_target_ids=tuple(dict.fromkeys(targets))),
        proposals=proposals,
    )
    ingress = {
        "schema": "rocell.model_motion_ingress.v2",
        "status": "ACCEPTED_V2_FOR_FRESH_SEQUENTIAL_PLANNER_GATES",
        "batch_sha256": batch.batch_sha256,
        "intent_plan_sha256": batch.intent_plan_sha256,
        "request_id": batch.request_id,
        "ordered_target_ids": list(targets),
        "controller_commands": [], "hardware_commands_generated": 0,
        "hardware_access": False, "physical_authority": False,
    }
    ingress["ingress_sha256"] = hashlib.sha256(_canonical(ingress)).hexdigest()
    config = TypingExecutionConfigV1(
        config_id="keyboard-offline", calibration_snapshot_sha256="f" * 64,
        tool_profile_sha256="0" * 64, dynamics_profile_sha256="1" * 64,
        route_reference_point=Point3Mm("board", -45.0, 0.0, 22.0),
        hover_clearance_mm=20.0, settle_position_tolerance_mm=0.5,
        settle_velocity_tolerance_mm_s=1.0, settle_hold_ms=100,
        preview_horizon=1, speed_class=SpeedClass.SLOW)
    return compile_typing_execution_plan_v1(batch, ingress, config=config)


def _policy(**overrides):
    values = dict(
        policy_id="keyboard-s0-quintic-v1", maximum_cartesian_step_mm=5.0,
        maximum_velocity_mm_s=80.0, maximum_acceleration_mm_s2=160.0,
        maximum_jerk_mm_s3=800.0, hover_settle_ms=100,
        contact_dwell_ms=60)
    values.update(overrides)
    return TypingTrajectoryPolicyV1(**values)


def test_compiles_ordered_endpoints_dense_samples_and_zero_authority():
    source = _execution_plan()
    plan = compile_typing_trajectory_plan_v1(source, policy=_policy())

    assert [item.target_id for item in plan.phase_waypoints if item.phase is MotionPhase.CONTACT] == [
        "H", "H", "1", "PERIOD"]
    assert plan.phase_waypoints[0].phase is plan.phase_waypoints[-1].phase is MotionPhase.PARK
    assert len(plan.phase_waypoints) == 2 + 3 * len(source.actions)
    assert all(
        math.dist(
            (left.point.x, left.point.y, left.point.z),
            (right.point.x, right.point.y, right.point.z),
        ) <= 5.0 + 1e-9
        for left, right in zip(plan.screening_samples, plan.screening_samples[1:])
    )
    document = plan.to_dict()
    assert document["status"] == STATUS
    assert document["ik_screening_executed"] is False
    assert document["collision_screening_executed"] is False
    assert document["controller_commands"] == []
    assert document["hardware_access"] is document["physical_authority"] is False


def test_quintic_profile_obeys_all_declared_cartesian_limits():
    policy = _policy()
    plan = compile_typing_trajectory_plan_v1(_execution_plan(), policy=policy)
    moving = [item for item in plan.timing_segments if item.distance_mm > 0.0]

    assert moving
    assert all(item.peak_velocity_mm_s <= policy.maximum_velocity_mm_s + 1e-9 for item in moving)
    assert all(item.peak_acceleration_mm_s2 <= policy.maximum_acceleration_mm_s2 + 1e-9 for item in moving)
    assert all(item.peak_jerk_mm_s3 <= policy.maximum_jerk_mm_s3 + 1e-9 for item in moving)
    assert all(item.limiting_constraint in {
        TimingConstraintV1.VELOCITY,
        TimingConstraintV1.ACCELERATION,
        TimingConstraintV1.JERK,
    } for item in moving)


def test_direct_route_beats_park_baseline_and_repeated_key_is_retained():
    source = _execution_plan(("H", "H", "1", "PERIOD"))
    plan = compile_typing_trajectory_plan_v1(source, policy=_policy())

    assert plan.metrics.direct_distance_mm == pytest.approx(source.metrics.direct_total_distance_mm)
    assert plan.metrics.park_baseline_distance_mm == pytest.approx(source.metrics.park_total_distance_mm)
    assert plan.metrics.direct_estimated_time_ms < plan.metrics.park_baseline_estimated_time_ms
    assert plan.metrics.estimated_time_saved_ms > 0.0
    repeated_hover = plan.timing_segments[3]
    assert repeated_hover.distance_mm == 0.0
    assert repeated_hover.limiting_constraint is TimingConstraintV1.ZERO_DISTANCE
    assert repeated_hover.dwell_after_ms == 100


def test_compilation_is_canonical_and_deterministic():
    source = _execution_plan()
    first = compile_typing_trajectory_plan_v1(source, policy=_policy())
    second = compile_typing_trajectory_plan_v1(source, policy=_policy())
    assert first.to_bytes() == second.to_bytes()
    assert first.trajectory_plan_sha256 == second.trajectory_plan_sha256
    assert json.loads(first.to_bytes())["trajectory_plan_sha256"] == first.trajectory_plan_sha256


def test_policy_rejects_unbounded_or_invalid_values():
    with pytest.raises(TypingTrajectoryPlanV1Error, match="maximum_cartesian_step_mm"):
        _policy(maximum_cartesian_step_mm=0.0)
    with pytest.raises(TypingTrajectoryPlanV1Error, match="maximum_jerk_mm_s3"):
        _policy(maximum_jerk_mm_s3=float("inf"))
    with pytest.raises(TypingTrajectoryPlanV1Error, match="contact_dwell_ms"):
        _policy(contact_dwell_ms=-1)
