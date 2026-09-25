from __future__ import annotations

from dataclasses import replace
import hashlib
import inspect
import json
from pathlib import Path
from typing import Iterator, cast

import pytest

from rocell.application.arm_camera_pose import (
    ARM_CAMERA_JOINT_ORDER,
    AchievedJointStateSource,
    AchievedModelJointPositions,
)
from rocell.application.bootstrap import bootstrap_virtual_workcell
from rocell.application.board_pose_correction import (
    BoardPoseCorrectionStatus,
    decide_board_pose_correction,
)
from rocell.application.runtime_ports import ArmFeedbackSample, RuntimeInstant
from rocell.application.virtual_arm_camera import (
    VIRTUAL_ARM_CAMERA_CLOCK,
    ArmCameraCaptureBracket,
    ArmCameraVisionQualityPolicy,
    VirtualArmCameraError,
    VirtualArmCameraCaptureMode,
    VirtualArmCameraStage,
    VirtualArmCameraVisionService,
    achieved_joint_sample_from_virtual_feedback,
    correction_measurement_from_vision_result,
    initial_planner_board_registration,
    make_hidden_virtual_board_truth,
    make_virtual_arm_camera_service,
    offset_synthetic_board_truth,
    planner_Wv_T_board,
)
from rocell.geometry import JointPosition, Vec3
from rocell.simulation.virtual_profile import (
    VirtualProfileContext,
    load_virtual_commissioning_profile,
)
from rocell.simulation.virtual_workcell import (
    VirtualArmFeedback,
    VirtualArmLifecycle,
)


WORKSPACE = Path(__file__).resolve().parents[3]
TICK_PERIOD_NS = 1_000_000
HOVER_T = (
    -0.23228866404719983,
    0.63981053780154,
    1.9887938075201332,
    -1.0578043436893252,
    4.987262088921639e-10,
)
HOVER_E = (
    -0.31131621748840294,
    0.6841707277884785,
    1.8469265148292362,
    -0.9602972424740397,
    4.2194931944696405e-10,
)


def _hash(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _state(context, values: tuple[float, ...]) -> AchievedModelJointPositions:  # type: ignore[no-untyped-def]
    complete = (*values, context.scenario.fixed_gripper_position.value)
    return AchievedModelJointPositions(
        positions=tuple(
            (name, JointPosition.radians(value))
            for name, value in zip(ARM_CAMERA_JOINT_ORDER, complete)
        ),
        source_kind=AchievedJointStateSource.VIRTUAL_PLANT,
        source_state_sha256=_hash(complete),
    )


def _bracket(context, values: tuple[float, ...] = HOVER_T) -> ArmCameraCaptureBracket:  # type: ignore[no-untyped-def]
    state = _state(context, values)
    before = ArmFeedbackSample(
        sample_id="hover-before-0009",
        observed_at=RuntimeInstant(
            VIRTUAL_ARM_CAMERA_CLOCK, 100, TICK_PERIOD_NS
        ),
        sequence=9,
        feedback=state,
    )
    after = ArmFeedbackSample(
        sample_id="hover-after-0009",
        observed_at=RuntimeInstant(
            VIRTUAL_ARM_CAMERA_CLOCK, 106, TICK_PERIOD_NS
        ),
        sequence=9,
        feedback=state,
    )
    return ArmCameraCaptureBracket(
        capture_sequence=9,
        before_feedback=before,
        after_feedback=after,
        settled_since=RuntimeInstant(
            VIRTUAL_ARM_CAMERA_CLOCK, 70, TICK_PERIOD_NS
        ),
        exposure_at=RuntimeInstant(
            VIRTUAL_ARM_CAMERA_CLOCK, 103, TICK_PERIOD_NS
        ),
    )


@pytest.fixture(scope="module")
def arm_camera_inputs():  # type: ignore[no-untyped-def]
    bootstrap = bootstrap_virtual_workcell(WORKSPACE)
    profile = load_virtual_commissioning_profile(
        cast(VirtualProfileContext, bootstrap.context)
    )
    truth_transform = offset_synthetic_board_truth(
        planner_Wv_T_board(profile.study_input),
        translation_Wv_mm=Vec3(1.0, -0.75, 0.2),
        yaw_board_rad=0.002,
    )
    truth = make_hidden_virtual_board_truth(
        profile.study_input,
        translation_Wv_mm=Vec3(1.0, -0.75, 0.2),
        yaw_board_rad=0.002,
    )
    service = make_virtual_arm_camera_service(
        bootstrap.context,
        profile.study_input,
        truth=truth,
    )
    return bootstrap.context, profile, service, truth, truth_transform


def _nested_values(value: object) -> Iterator[object]:
    yield value
    if isinstance(value, dict):
        for child in value.values():
            yield from _nested_values(child)
    elif isinstance(value, (list, tuple)):
        for child in value:
            yield from _nested_values(child)


def test_processor_signature_cannot_receive_action_target_or_pose_truth() -> None:
    assert tuple(
        inspect.signature(VirtualArmCameraVisionService.process).parameters
    ) == ("self", "bracket", "capture_mode")


def test_joint_dependent_pixels_recover_offset_board_pose(arm_camera_inputs) -> None:  # type: ignore[no-untyped-def]
    context, _, service, truth_source, truth_transform = arm_camera_inputs
    first = service.process(bracket=_bracket(context, HOVER_T))
    second = service.process(
        bracket=replace(_bracket(context, HOVER_E), capture_sequence=10)
    )

    assert first.passed and second.passed
    assert first.stage is VirtualArmCameraStage.COMPLETE
    assert first.arm_camera_pose is not None
    assert second.arm_camera_pose is not None
    assert not first.arm_camera_pose.Wv_T_C_arm.almost_equal(
        second.arm_camera_pose.Wv_T_C_arm, absolute_tolerance=1e-9
    )
    assert first.rendered_frame is not None and second.rendered_frame is not None
    assert (
        first.rendered_frame.frame_packet.jpeg_bytes
        != second.rendered_frame.frame_packet.jpeg_bytes
    )
    assert first.detection_batch is not None
    assert len(first.detection_batch.accepted_tags) >= 4
    assert first.pose_observation is not None
    assert first.pose_observation.pose.parent_frame == "C_arm"
    assert first.pose_observation.pose.child_frame == "board"
    assert first.quality is not None and first.quality.passed

    observed = first.observed_Wv_T_board
    assert observed is not None
    assert (
        observed.translation_mm - truth_transform.translation_mm
    ).norm < 1.0
    assert (
        service.definition_dict()["private_truth_registration_sha256"]
        == truth_source.content_hash
    )

    document = first.to_dict()
    serialized = json.dumps(document, sort_keys=True)
    assert document["target_or_action_received_by_processor"] is False
    assert document["synthetic_truth_transform_serialized"] is False
    assert document["jpeg_bytes_serialized"] is False
    assert "private_synthetic_board_truth" not in serialized
    assert not any(isinstance(value, bytes) for value in _nested_values(document))


def test_timing_and_motion_faults_stop_before_detection(arm_camera_inputs) -> None:  # type: ignore[no-untyped-def]
    context, _, service, _, _ = arm_camera_inputs
    normal = _bracket(context)

    stale = service.process(
        bracket=replace(
            normal,
            before_feedback=replace(normal.before_feedback, stale=True),
        )
    )
    assert not stale.passed
    assert stale.stage is VirtualArmCameraStage.SYNCHRONIZATION
    assert stale.detail_code == "ARM_CAMERA_FEEDBACK_STALE"
    assert stale.rendered_frame is None

    wrong_clock = service.process(
        bracket=replace(
            normal,
            exposure_at=RuntimeInstant("other_clock", 103, TICK_PERIOD_NS),
        )
    )
    assert wrong_clock.detail_code == "ARM_CAMERA_CLOCK_MISMATCH"
    assert wrong_clock.rendered_frame is None

    moved_state = _state(context, HOVER_E)
    moved_after = replace(normal.after_feedback, feedback=moved_state)
    moved = service.process(bracket=replace(normal, after_feedback=moved_after))
    assert moved.detail_code == "ARM_CAMERA_JOINTS_MOVED_DURING_CAPTURE"
    assert moved.rendered_frame is None


def test_capture_requires_two_distinct_samples_strictly_around_exposure(
    arm_camera_inputs,
) -> None:  # type: ignore[no-untyped-def]
    context, _, service, _, _ = arm_camera_inputs
    normal = _bracket(context)

    duplicated = service.process(
        bracket=replace(
            normal,
            after_feedback=normal.before_feedback,
        )
    )
    assert duplicated.detail_code == "ARM_CAMERA_FEEDBACK_BRACKET_NOT_DISTINCT"
    assert duplicated.rendered_frame is None

    exposure_at_before = service.process(
        bracket=replace(
            normal,
            exposure_at=normal.before_feedback.observed_at,
        )
    )
    assert exposure_at_before.detail_code == "ARM_CAMERA_BRACKET_ORDER_INVALID"
    assert exposure_at_before.rendered_frame is None


def test_capture_accepts_only_virtual_plant_feedback_inside_controller_limits(
    arm_camera_inputs,
) -> None:  # type: ignore[no-untyped-def]
    context, _, service, _, _ = arm_camera_inputs
    normal = _bracket(context)

    offline_state = replace(
        normal.before_feedback.feedback,
        source_kind=AchievedJointStateSource.OFFLINE_FEEDBACK_PROJECTION,
    )
    offline = service.process(
        bracket=replace(
            normal,
            before_feedback=replace(
                normal.before_feedback,
                feedback=offline_state,
            ),
            after_feedback=replace(
                normal.after_feedback,
                feedback=offline_state,
            ),
        )
    )
    assert offline.detail_code == "ARM_CAMERA_FEEDBACK_SOURCE_NOT_VIRTUAL_PLANT"
    assert offline.rendered_frame is None

    positions = list(normal.before_feedback.feedback.positions)
    first_name, _ = positions[0]
    controller_upper = (
        context.scenario.controller_joint_intersection_rad[first_name][1]
    )
    positions[0] = (
        first_name,
        JointPosition.radians(controller_upper + 1e-7),
    )
    outside_state = replace(
        normal.before_feedback.feedback,
        positions=tuple(positions),
        source_state_sha256=_hash(
            tuple(position.value for _, position in positions)
        ),
    )
    outside = service.process(
        bracket=replace(
            normal,
            before_feedback=replace(
                normal.before_feedback,
                feedback=outside_state,
            ),
            after_feedback=replace(
                normal.after_feedback,
                feedback=outside_state,
            ),
        )
    )
    assert outside.detail_code == "ARM_CAMERA_FEEDBACK_OUTSIDE_CONTROLLER_LIMITS"
    assert outside.rendered_frame is None

    definition = service.definition_dict()
    assert definition["accepted_joint_state_source"] == "VIRTUAL_PLANT"
    assert definition["controller_joint_intersection_rad"] == {
        name: list(context.scenario.controller_joint_intersection_rad[name])
        for name in ARM_CAMERA_JOINT_ORDER[:-1]
    }
    assert definition["controller_gripper_intersection_rad"] == list(
        context.scenario.controller_gripper_intersection_rad
    )


def test_quality_decision_is_recomputed_and_fault_pose_accessor_is_closed(
    arm_camera_inputs,
) -> None:  # type: ignore[no-untyped-def]
    context, _, service, truth, _ = arm_camera_inputs
    strict = VirtualArmCameraVisionService(
        context=context,
        binding=service.binding,
        truth=truth,
        quality_policy=ArmCameraVisionQualityPolicy(
            maximum_covariance_diagonal=1e-12
        ),
    )
    rejected = strict.process(bracket=_bracket(context))

    assert rejected.status == "FAULT"
    assert rejected.stage is VirtualArmCameraStage.QUALITY
    assert rejected.quality is not None
    assert not rejected.quality.passed
    assert rejected.pose_observation is not None
    assert rejected.observed_Wv_T_board is None

    forged_quality = replace(rejected.quality, covariance_passed=True)
    with pytest.raises(VirtualArmCameraError, match="quality gate flags"):
        replace(
            rejected,
            status="PASS",
            stage=VirtualArmCameraStage.COMPLETE,
            detail_code="ARM_CAMERA_BOARD_POSE_ACCEPTED",
            quality=forged_quality,
        )

    passing = service.process(bracket=_bracket(context))
    assert passing.passed
    with pytest.raises(VirtualArmCameraError, match="result status"):
        replace(passing, status="FAULT")

    with pytest.raises(VirtualArmCameraError, match="maximum_inlier_rmse_px"):
        ArmCameraVisionQualityPolicy(maximum_inlier_rmse_px=1e-7)


def test_pixel_and_frame_faults_cross_the_real_jpeg_boundary(arm_camera_inputs) -> None:  # type: ignore[no-untyped-def]
    context, _, service, _, _ = arm_camera_inputs
    bracket = _bracket(context)
    normal = service.process(bracket=bracket)
    assert normal.rendered_frame is not None

    for mode in (
        VirtualArmCameraCaptureMode.TAG_LOSS,
        VirtualArmCameraCaptureMode.EXCESS_BLUR,
        VirtualArmCameraCaptureMode.EXCESS_NOISE,
    ):
        result = service.process(bracket=bracket, capture_mode=mode)
        assert not result.passed
        assert result.rendered_frame is not None
        assert (
            result.rendered_frame.frame_packet.sha256
            != normal.rendered_frame.frame_packet.sha256
        )

    unavailable = service.process(
        bracket=bracket,
        capture_mode=VirtualArmCameraCaptureMode.CAMERA_UNAVAILABLE,
    )
    assert unavailable.stage is VirtualArmCameraStage.CAPTURE
    assert unavailable.rendered_frame is None

    unqualified = service.process(
        bracket=bracket,
        capture_mode=VirtualArmCameraCaptureMode.UNQUALIFIED_TIMESTAMP,
    )
    assert unqualified.stage is VirtualArmCameraStage.SYNCHRONIZATION
    assert unqualified.detail_code == "ARM_CAMERA_FRAME_TIMESTAMP_UNQUALIFIED"
    assert unqualified.rendered_frame is not None

    stale_frame = service.process(
        bracket=bracket,
        capture_mode=VirtualArmCameraCaptureMode.STALE_FRAME,
    )
    assert stale_frame.detail_code == "ARM_CAMERA_FRAME_SEQUENCE_STALE"
    assert stale_frame.rendered_frame is not None


def test_virtual_feedback_adapter_requires_and_hashes_explicit_gripper(
    arm_camera_inputs,
) -> None:  # type: ignore[no-untyped-def]
    context, _, _, _, _ = arm_camera_inputs
    feedback = VirtualArmFeedback(
        tick=22,
        lifecycle=VirtualArmLifecycle.EXECUTING,
        joint_positions_rad=tuple(
            (name, value)
            for name, value in zip(ARM_CAMERA_JOINT_ORDER[:-1], HOVER_T)
        ),
        last_waypoint_sequence=9,
        last_action_index=0,
        virtual_commands_executed=1,
        plant_state_hash="a" * 64,
    )
    sample = achieved_joint_sample_from_virtual_feedback(
        feedback,
        fixed_gripper_position=context.scenario.fixed_gripper_position,
        sample_id="adapted-hover-9",
        observed_at=RuntimeInstant(
            VIRTUAL_ARM_CAMERA_CLOCK, 22, TICK_PERIOD_NS
        ),
    )
    assert tuple(sample.feedback.positions_by_name) == ARM_CAMERA_JOINT_ORDER
    assert sample.feedback.positions[-1][1] == context.scenario.fixed_gripper_position
    assert sample.sequence == feedback.last_waypoint_sequence

    changed = achieved_joint_sample_from_virtual_feedback(
        feedback,
        fixed_gripper_position=JointPosition.radians(
            context.scenario.fixed_gripper_position.value + 0.01
        ),
        sample_id="adapted-hover-9-other-gripper",
        observed_at=sample.observed_at,
    )
    assert changed.feedback.source_state_sha256 != (
        sample.feedback.source_state_sha256
    )


def test_passing_pixels_feed_a_bounded_apply_decision_without_truth_input(
    arm_camera_inputs,
) -> None:  # type: ignore[no-untyped-def]
    context, profile, service, _, _ = arm_camera_inputs
    result = service.process(bracket=_bracket(context))
    assert result.passed
    measurement = correction_measurement_from_vision_result(
        result,
        previous_source_sequence=8,
        previous_freshness_token="prior-arm-camera-frame",
        evaluated_at=RuntimeInstant(
            VIRTUAL_ARM_CAMERA_CLOCK, 108, TICK_PERIOD_NS
        ),
    )
    active = initial_planner_board_registration(profile.study_input)
    decision = decide_board_pose_correction(active, measurement)

    assert decision.status is BoardPoseCorrectionStatus.APPLY
    assert 0.5 < decision.translation_delta_norm_mm < 2.0
    assert decision.rejection_reasons == ()
    assert decision.selected_registration_hash == (
        decision.candidate_registration.registration_hash
    )
    assert decision.to_dict()["candidate_installed"] is False
    # The candidate comes only from FK * observed pose.  The service's hidden
    # truth is not an input to either measurement construction or the decider.
    assert measurement.Wv_T_board_candidate.almost_equal(
        result.observed_Wv_T_board, absolute_tolerance=0.0  # type: ignore[arg-type]
    )
