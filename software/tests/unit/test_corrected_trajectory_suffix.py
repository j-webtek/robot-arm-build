from __future__ import annotations

from dataclasses import dataclass, replace
import hashlib
import inspect
import json
from pathlib import Path
from typing import Iterator, Mapping, cast

import pytest

from rocell.application.actual_contact_geometry import (
    ActualToolTipContactGeometry,
    ActualToolTipContactProjector,
)
from rocell.application.arm_camera_pose import (
    ARM_CAMERA_JOINT_ORDER,
    AchievedJointStateSource,
    AchievedModelJointPositions,
    achieved_joint_sample_sha256,
)
from rocell.application.board_pose_correction import (
    ArmCameraBoardMeasurement,
    BoardPoseCorrectionDecision,
    BoardPoseCorrectionPolicy,
    BoardPoseCorrectionStatus,
    decide_board_pose_correction,
)
from rocell.application.bootstrap import (
    VirtualWorkcellBootstrap,
    bootstrap_virtual_workcell,
)
from rocell.application.corrected_trajectory_suffix import (
    CorrectionPathRole,
    CorrectedTrajectorySuffix,
    CorrectedTrajectorySuffixError,
    replan_corrected_trajectory_suffix,
)
from rocell.application.runtime_ports import ArmFeedbackSample, RuntimeInstant
from rocell.application.trajectory_simulation import (
    CartesianRouteWaypoint,
    JointTrajectoryWaypointResult,
    TrajectorySimulationPolicy,
    TrajectorySimulationReport,
    run_trajectory_simulation,
)
from rocell.application.virtual_arm_camera import (
    VIRTUAL_ARM_CAMERA_CLOCK,
    ArmCameraCaptureBracket,
    VirtualArmCameraVisionResult,
    correction_measurement_from_vision_result,
    initial_planner_board_registration,
    make_hidden_virtual_board_truth,
    make_virtual_arm_camera_service,
)
from rocell.application.virtual_board_truth import HiddenVirtualBoardTruth
from rocell.application.virtual_session import build_virtual_device_model
from rocell.geometry import JointPosition, Vec3
from rocell.kinematics import ARM_JOINT_NAMES
from rocell.models.actions import ActionPlan
from rocell.motion import MotionPhase
from rocell.simulation.virtual_profile import (
    VirtualCommissioningProfile,
    VirtualProfileContext,
    load_virtual_commissioning_profile,
)
from rocell.simulation.virtual_workcell import ContactDisposition, ContactEvent
from rocell.typing import compile_development_text


WORKSPACE = Path(__file__).resolve().parents[3]
TICK_PERIOD_NS = 1_000_000
TRUTH_TRANSLATION_WV_MM = Vec3(12.0, 0.0, 0.0)


def _stable_hash(value: object) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()


def _mapping_nodes(value: object) -> Iterator[Mapping[str, object]]:
    if isinstance(value, Mapping):
        yield value
        for child in value.values():
            yield from _mapping_nodes(child)
    elif isinstance(value, (tuple, list)):
        for child in value:
            yield from _mapping_nodes(child)


def _achieved_state(
    bootstrap: VirtualWorkcellBootstrap,
    arm_positions_rad: Mapping[str, float],
    *,
    state_id: str,
) -> AchievedModelJointPositions:
    complete = tuple(
        arm_positions_rad[name] for name in ARM_CAMERA_JOINT_ORDER[:-1]
    ) + (bootstrap.context.scenario.fixed_gripper_position.value,)
    return AchievedModelJointPositions(
        positions=tuple(
            (name, JointPosition.radians(value))
            for name, value in zip(ARM_CAMERA_JOINT_ORDER, complete)
        ),
        source_kind=AchievedJointStateSource.VIRTUAL_PLANT,
        source_state_sha256=_stable_hash(
            {
                "state_id": state_id,
                "positions_rad": dict(zip(ARM_CAMERA_JOINT_ORDER, complete)),
            }
        ),
    )


def _feedback_sample(
    state: AchievedModelJointPositions,
    *,
    sample_id: str,
    tick: int,
    sequence: int,
) -> ArmFeedbackSample[AchievedModelJointPositions]:
    return ArmFeedbackSample(
        sample_id=sample_id,
        observed_at=RuntimeInstant(
            VIRTUAL_ARM_CAMERA_CLOCK,
            tick,
            TICK_PERIOD_NS,
        ),
        sequence=sequence,
        feedback=state,
    )


@dataclass(frozen=True, slots=True)
class _ShiftedSuffixScenario:
    bootstrap: VirtualWorkcellBootstrap
    profile: VirtualCommissioningProfile
    plan: ActionPlan
    trajectory: TrajectorySimulationReport
    hover_index: int
    hover_waypoint: CartesianRouteWaypoint
    hover_result: JointTrajectoryWaypointResult
    achieved_arm_positions_rad: Mapping[str, float]
    capture_bracket: ArmCameraCaptureBracket
    truth: HiddenVirtualBoardTruth
    vision_result: VirtualArmCameraVisionResult
    measurement: ArmCameraBoardMeasurement
    decision: BoardPoseCorrectionDecision
    suffix: CorrectedTrajectorySuffix


@pytest.fixture(scope="module")
def shifted_suffix() -> _ShiftedSuffixScenario:
    bootstrap = bootstrap_virtual_workcell(WORKSPACE)
    profile = load_virtual_commissioning_profile(
        cast(VirtualProfileContext, bootstrap.context)
    )
    plan = compile_development_text("keyboard", "a")
    park = profile.park_point_board
    trajectory = run_trajectory_simulation(
        bootstrap.context,
        plan,
        profile.study_input,
        TrajectorySimulationPolicy(
            maximum_route_targets=8,
            park_xy_board_mm=(park.x, park.y),
        ),
    )
    final = trajectory.final_round
    assert final is not None and final.all_waypoints_accepted
    hover_index = next(
        index
        for index, waypoint in enumerate(final.waypoints)
        if waypoint.phase is MotionPhase.HOVER and waypoint.phase_endpoint
    )
    hover = final.waypoints[hover_index]
    hover_result = final.joint_results[hover_index]
    achieved = dict(hover_result.solution_arm_joint_positions_rad)
    state = _achieved_state(bootstrap, achieved, state_id="executed-source-hover")
    capture_bracket = ArmCameraCaptureBracket(
        capture_sequence=hover.sequence,
        before_feedback=_feedback_sample(
            state,
            sample_id="shifted-hover-before",
            tick=100,
            sequence=hover.sequence,
        ),
        after_feedback=_feedback_sample(
            state,
            sample_id="shifted-hover-after",
            tick=106,
            sequence=hover.sequence,
        ),
        settled_since=RuntimeInstant(
            VIRTUAL_ARM_CAMERA_CLOCK,
            70,
            TICK_PERIOD_NS,
        ),
        exposure_at=RuntimeInstant(
            VIRTUAL_ARM_CAMERA_CLOCK,
            103,
            TICK_PERIOD_NS,
        ),
    )

    # This one private truth object is injected into the raster camera here and
    # into the independent achieved-contact projector in the contact test.
    truth = make_hidden_virtual_board_truth(
        profile.study_input,
        translation_Wv_mm=TRUTH_TRANSLATION_WV_MM,
    )
    service = make_virtual_arm_camera_service(
        bootstrap.context,
        profile.study_input,
        truth=truth,
    )
    vision_result = service.process(bracket=capture_bracket)
    assert vision_result.passed
    assert (
        service.definition_dict()["private_truth_registration_sha256"]
        == truth.content_hash
    )
    measurement = correction_measurement_from_vision_result(
        vision_result,
        previous_source_sequence=hover.sequence - 1,
        previous_freshness_token="prior-arm-camera-frame",
        evaluated_at=RuntimeInstant(
            VIRTUAL_ARM_CAMERA_CLOCK,
            108,
            TICK_PERIOD_NS,
        ),
    )
    decision = decide_board_pose_correction(
        initial_planner_board_registration(profile.study_input),
        measurement,
    )
    suffix = replan_corrected_trajectory_suffix(
        bootstrap.context,
        trajectory,
        decision,
        hover_waypoint_sequence=hover.sequence,
        previous_execution_sequence=hover.sequence,
        achieved_feedback_sample=capture_bracket.after_feedback,
    )
    return _ShiftedSuffixScenario(
        bootstrap=bootstrap,
        profile=profile,
        plan=plan,
        trajectory=trajectory,
        hover_index=hover_index,
        hover_waypoint=hover,
        hover_result=hover_result,
        achieved_arm_positions_rad=achieved,
        capture_bracket=capture_bracket,
        truth=truth,
        vision_result=vision_result,
        measurement=measurement,
        decision=decision,
        suffix=suffix,
    )


def test_twelve_mm_shift_is_observed_applied_and_fully_replanned(
    shifted_suffix: _ShiftedSuffixScenario,
) -> None:
    decision = shifted_suffix.decision
    suffix = shifted_suffix.suffix

    assert decision.status is BoardPoseCorrectionStatus.APPLY
    assert decision.rejection_reasons == ()
    # Pixel quantization and planar-pose fitting are allowed to contribute a
    # small error; the measurement still recovers the deliberately large shift.
    assert decision.translation_delta_norm_mm == pytest.approx(12.0, abs=0.5)
    assert suffix.passed
    assert suffix.termination_reason == "ALL_REPLACEMENT_WAYPOINTS_ACCEPTED"
    assert len(suffix.waypoints) == len(suffix.joint_results) > 0
    assert all(check.passed for check in suffix.segment_checks)
    assert all(result.accepted for result in suffix.joint_results)
    assert suffix.correction_decision.decision_hash == decision.decision_hash
    assert suffix.source_trajectory_sha256 == shifted_suffix.trajectory.report_hash


def test_execution_source_and_revision_identities_remain_distinct(
    shifted_suffix: _ShiftedSuffixScenario,
) -> None:
    suffix = shifted_suffix.suffix
    execution_sequences = tuple(
        waypoint.execution_sequence for waypoint in suffix.waypoints
    )
    source_sequences = tuple(
        waypoint.source_waypoint_sequence for waypoint in suffix.waypoints
    )

    assert execution_sequences == tuple(
        range(
            shifted_suffix.hover_waypoint.sequence + 1,
            shifted_suffix.hover_waypoint.sequence + 1 + len(suffix.waypoints),
        )
    )
    assert suffix.trajectory_revision == shifted_suffix.decision.candidate_registration.revision
    assert suffix.trajectory_revision == 1
    assert all(
        waypoint.trajectory_revision == suffix.trajectory_revision
        for waypoint in suffix.waypoints
    )
    assert any(source is None for source in source_sequences)
    assert any(
        source is not None and source != execution
        for source, execution in zip(source_sequences, execution_sequences)
    )
    # Refinement can map several new commands to one retained Cartesian source;
    # a source sequence is therefore not an execution command identifier.
    retained = tuple(source for source in source_sequences if source is not None)
    assert len(retained) > len(set(retained))
    correction_roles = {
        CorrectionPathRole.ASCEND_TO_CORRECTION_PLANE,
        CorrectionPathRole.LATERAL_ON_CORRECTION_PLANE,
        CorrectionPathRole.DESCEND_TO_CORRECTED_HOVER,
    }
    assert all(
        waypoint.source_waypoint_sequence is None
        for waypoint in suffix.waypoints
        if waypoint.path_role in correction_roles
    )


def test_unexecuted_nominal_joint_results_are_discarded_not_reused(
    shifted_suffix: _ShiftedSuffixScenario,
) -> None:
    final = shifted_suffix.trajectory.final_round
    assert final is not None
    old_results = final.joint_results[shifted_suffix.hover_index + 1 :]
    new_results = shifted_suffix.suffix.joint_results

    assert old_results and new_results
    assert not any(new is old for new in new_results for old in old_results)
    assert shifted_suffix.suffix.to_dict()["replacement_boundary"] == {
        "after_source_hover_sequence": shifted_suffix.hover_waypoint.sequence,
        "previous_execution_sequence": shifted_suffix.hover_waypoint.sequence,
        "caller_must_discard_all_old_joint_results_after_boundary": True,
        "atomic_queue_replacement_verified_here": False,
    }
    old_contact = next(
        result
        for result in old_results
        if result.phase is MotionPhase.CONTACT and result.action_index == 0
    )
    new_contact = next(
        result
        for waypoint, result in zip(
            shifted_suffix.suffix.waypoints,
            shifted_suffix.suffix.joint_results,
        )
        if waypoint.phase is MotionPhase.CONTACT and waypoint.phase_endpoint
    )
    assert new_contact.solution_arm_joint_positions_rad != (
        old_contact.solution_arm_joint_positions_rad
    )


def test_non_apply_wrong_hover_and_excessive_tracking_error_fail_closed(
    shifted_suffix: _ShiftedSuffixScenario,
) -> None:
    active = shifted_suffix.decision.active_registration
    no_change = decide_board_pose_correction(
        active,
        shifted_suffix.measurement,
        BoardPoseCorrectionPolicy(translation_deadband_mm=13.0),
    )
    assert no_change.status is BoardPoseCorrectionStatus.NO_CHANGE
    with pytest.raises(
        CorrectedTrajectorySuffixError,
        match="only an APPLY correction decision",
    ):
        replan_corrected_trajectory_suffix(
            shifted_suffix.bootstrap.context,
            shifted_suffix.trajectory,
            no_change,
            hover_waypoint_sequence=shifted_suffix.hover_waypoint.sequence,
            previous_execution_sequence=shifted_suffix.hover_waypoint.sequence,
            achieved_feedback_sample=shifted_suffix.capture_bracket.after_feedback,
        )

    final = shifted_suffix.trajectory.final_round
    assert final is not None
    wrong_boundary = next(
        waypoint for waypoint in final.waypoints if waypoint.phase is not MotionPhase.HOVER
    )
    with pytest.raises(
        CorrectedTrajectorySuffixError,
        match="physical-action HOVER endpoint",
    ):
        replan_corrected_trajectory_suffix(
            shifted_suffix.bootstrap.context,
            shifted_suffix.trajectory,
            shifted_suffix.decision,
            hover_waypoint_sequence=wrong_boundary.sequence,
            previous_execution_sequence=wrong_boundary.sequence,
            achieved_feedback_sample=shifted_suffix.capture_bracket.after_feedback,
        )

    changed_achieved = dict(shifted_suffix.achieved_arm_positions_rad)
    changed_achieved[ARM_JOINT_NAMES[0]] += (
        shifted_suffix.trajectory.policy.maximum_joint_step_rad + 1e-3
    )
    changed_state = _achieved_state(
        shifted_suffix.bootstrap,
        changed_achieved,
        state_id="excessive-hover-tracking-error",
    )
    with pytest.raises(
        CorrectedTrajectorySuffixError,
        match="tracking error exceeds",
    ):
        replan_corrected_trajectory_suffix(
            shifted_suffix.bootstrap.context,
            shifted_suffix.trajectory,
            shifted_suffix.decision,
            hover_waypoint_sequence=shifted_suffix.hover_waypoint.sequence,
            previous_execution_sequence=shifted_suffix.hover_waypoint.sequence,
            achieved_feedback_sample=_feedback_sample(
                changed_state,
                sample_id="excessive-hover-tracking-error",
                tick=109,
                sequence=shifted_suffix.hover_waypoint.sequence,
            ),
        )


def test_replan_requires_fresh_correlated_virtual_plant_feedback(
    shifted_suffix: _ShiftedSuffixScenario,
) -> None:
    sample = shifted_suffix.capture_bracket.after_feedback
    arguments = {
        "hover_waypoint_sequence": shifted_suffix.hover_waypoint.sequence,
        "previous_execution_sequence": shifted_suffix.hover_waypoint.sequence,
    }
    with pytest.raises(CorrectedTrajectorySuffixError, match="stale"):
        replan_corrected_trajectory_suffix(
            shifted_suffix.bootstrap.context,
            shifted_suffix.trajectory,
            shifted_suffix.decision,
            achieved_feedback_sample=replace(sample, stale=True),
            **arguments,
        )
    with pytest.raises(CorrectedTrajectorySuffixError, match="sequence differs"):
        replan_corrected_trajectory_suffix(
            shifted_suffix.bootstrap.context,
            shifted_suffix.trajectory,
            shifted_suffix.decision,
            achieved_feedback_sample=replace(sample, sequence=sample.sequence + 1),
            **arguments,
        )
    offline = replace(
        sample.feedback,
        source_kind=AchievedJointStateSource.OFFLINE_FEEDBACK_PROJECTION,
    )
    with pytest.raises(CorrectedTrajectorySuffixError, match="VIRTUAL_PLANT"):
        replan_corrected_trajectory_suffix(
            shifted_suffix.bootstrap.context,
            shifted_suffix.trajectory,
            shifted_suffix.decision,
            achieved_feedback_sample=replace(sample, feedback=offline),
            **arguments,
        )


def test_small_achieved_tracking_error_is_used_and_hash_bound(
    shifted_suffix: _ShiftedSuffixScenario,
) -> None:
    shifted = dict(shifted_suffix.achieved_arm_positions_rad)
    shifted[ARM_JOINT_NAMES[0]] += 1e-6
    state = _achieved_state(
        shifted_suffix.bootstrap,
        shifted,
        state_id="small-genuine-tracking-error",
    )
    sample = _feedback_sample(
        state,
        sample_id="small-genuine-tracking-error",
        tick=109,
        sequence=shifted_suffix.hover_waypoint.sequence,
    )
    suffix = replan_corrected_trajectory_suffix(
        shifted_suffix.bootstrap.context,
        shifted_suffix.trajectory,
        shifted_suffix.decision,
        hover_waypoint_sequence=shifted_suffix.hover_waypoint.sequence,
        previous_execution_sequence=shifted_suffix.hover_waypoint.sequence,
        achieved_feedback_sample=sample,
    )

    assert suffix.passed
    assert suffix.achieved_joint_state_sha256 == achieved_joint_sample_sha256(sample)
    assert suffix.achieved_maximum_tracking_error_rad == pytest.approx(1e-6)
    assert suffix.maximum_allowed_tracking_error_rad == (
        shifted_suffix.trajectory.policy.maximum_joint_step_rad
    )
    tracking_document = cast(
        Mapping[str, object],
        suffix.to_dict()["achieved_hover_tracking"],
    )
    assert tracking_document["passed"] is True


def test_replacement_obeys_source_waypoint_and_solve_caps(
    shifted_suffix: _ShiftedSuffixScenario,
) -> None:
    constrained = replace(
        shifted_suffix.trajectory,
        policy=replace(
            shifted_suffix.trajectory.policy,
            maximum_waypoints_per_round=8,
            maximum_total_ik_solves=8,
        ),
    )
    with pytest.raises(
        CorrectedTrajectorySuffixError,
        match="source trajectory resource policy",
    ):
        replan_corrected_trajectory_suffix(
            shifted_suffix.bootstrap.context,
            constrained,
            shifted_suffix.decision,
            hover_waypoint_sequence=shifted_suffix.hover_waypoint.sequence,
            previous_execution_sequence=shifted_suffix.hover_waypoint.sequence,
            achieved_feedback_sample=shifted_suffix.capture_bracket.after_feedback,
        )


def test_suffix_is_zero_authority_and_hash_deterministic(
    shifted_suffix: _ShiftedSuffixScenario,
) -> None:
    first = shifted_suffix.suffix
    second = replan_corrected_trajectory_suffix(
        shifted_suffix.bootstrap.context,
        shifted_suffix.trajectory,
        shifted_suffix.decision,
        hover_waypoint_sequence=shifted_suffix.hover_waypoint.sequence,
        previous_execution_sequence=shifted_suffix.hover_waypoint.sequence,
        achieved_feedback_sample=shifted_suffix.capture_bracket.after_feedback,
    )

    assert first.to_dict() == second.to_dict()
    assert first.suffix_hash == second.suffix_hash
    assert first.suffix_hash == _stable_hash(first.to_dict())
    document = first.to_dict()
    assert document["simulation_only"] is True
    assert document["unsupported_physical_checks"]
    for node in _mapping_nodes(document):
        if "hardware_accessed" in node:
            assert node["hardware_accessed"] is False
        if "hardware_commands_generated" in node:
            assert node["hardware_commands_generated"] == 0
        if "live_motion_authorized" in node:
            assert node["live_motion_authorized"] is False
        if "physical_contact_authorized" in node:
            assert node["physical_contact_authorized"] is False
        if "physical_release_effect" in node:
            assert node["physical_release_effect"] == "NONE"


def test_replan_contract_cannot_receive_hidden_truth() -> None:
    parameters = inspect.signature(replan_corrected_trajectory_suffix).parameters
    assert tuple(parameters) == (
        "context",
        "trajectory",
        "correction_decision",
        "hover_waypoint_sequence",
        "previous_execution_sequence",
        "achieved_feedback_sample",
    )
    assert not any("truth" in name.lower() for name in parameters)


def _project_contact(
    shifted: _ShiftedSuffixScenario,
    projector: ActualToolTipContactProjector,
    result: JointTrajectoryWaypointResult,
    *,
    state_id: str,
    tick: int,
) -> ActualToolTipContactGeometry:
    state = _achieved_state(
        shifted.bootstrap,
        dict(result.solution_arm_joint_positions_rad),
        state_id=state_id,
    )
    return projector.project(
        _feedback_sample(
            state,
            sample_id=state_id,
            tick=tick,
            sequence=result.waypoint_sequence,
        )
    )


def _contact_event(geometry: ActualToolTipContactGeometry) -> ContactEvent:
    point = geometry.tip_position_truth_board_mm
    axis = geometry.hand_tcp_z_axis_truth_board
    return ContactEvent(
        action_index=0,
        achieved_board_xyz_mm=(point.x, point.y, point.z),
        achieved_contact_normal_board=(-axis.x, -axis.y, -axis.z),
        dwell_ticks=1,
    )


def test_corrected_achieved_contact_hits_a_while_old_nominal_contact_misses(
    shifted_suffix: _ShiftedSuffixScenario,
) -> None:
    final = shifted_suffix.trajectory.final_round
    assert final is not None
    original_contact = next(
        result
        for waypoint, result in zip(final.waypoints, final.joint_results)
        if waypoint.phase is MotionPhase.CONTACT and waypoint.phase_endpoint
    )
    corrected_contact = next(
        result
        for waypoint, result in zip(
            shifted_suffix.suffix.waypoints,
            shifted_suffix.suffix.joint_results,
        )
        if waypoint.phase is MotionPhase.CONTACT and waypoint.phase_endpoint
    )
    projector = ActualToolTipContactProjector(
        model_path=shifted_suffix.bootstrap.context.scenario.model_path,
        tool_length_mm=shifted_suffix.trajectory.tool_length_mm,
        truth=shifted_suffix.truth,
        joint_bounds_rad=(
            shifted_suffix.bootstrap.context.scenario.controller_joint_intersection_rad
        ),
        gripper_bounds_rad=(
            shifted_suffix.bootstrap.context.scenario.controller_gripper_intersection_rad
        ),
    )
    original_geometry = _project_contact(
        shifted_suffix,
        projector,
        original_contact,
        state_id="old-nominal-contact",
        tick=200,
    )
    corrected_geometry = _project_contact(
        shifted_suffix,
        projector,
        corrected_contact,
        state_id="corrected-contact",
        tick=201,
    )

    target_a = shifted_suffix.bootstrap.context.targets.keyboard_targets["A"]
    left, front, right, rear = target_a.safe_rectangle_board_mm
    corrected_point = corrected_geometry.tip_position_truth_board_mm
    original_point = original_geometry.tip_position_truth_board_mm
    assert left <= corrected_point.x <= right
    assert front <= corrected_point.y <= rear
    assert not (
        left <= original_point.x <= right
        and front <= original_point.y <= rear
    )

    # The independent device model receives only truth-projected achieved
    # geometry.  No planned target ID or expected character enters the event.
    corrected_device, corrected_count = build_virtual_device_model(
        shifted_suffix.bootstrap,
        shifted_suffix.plan,
        "a",
    )
    original_device, original_count = build_virtual_device_model(
        shifted_suffix.bootstrap,
        shifted_suffix.plan,
        "a",
    )
    assert corrected_count == original_count == 1
    corrected_resolution = corrected_device.apply_contact(
        _contact_event(corrected_geometry)
    )
    original_resolution = original_device.apply_contact(
        _contact_event(original_geometry)
    )
    assert corrected_resolution.disposition is ContactDisposition.ACCEPTED
    assert corrected_resolution.resolved_target_id == "keyboard:A"
    assert corrected_resolution.emitted_output == "a"
    assert original_resolution.disposition is ContactDisposition.OUTSIDE_REGION
    assert original_resolution.resolved_target_id is None
