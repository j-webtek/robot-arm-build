from __future__ import annotations

from collections.abc import Iterator, Mapping
from dataclasses import replace
import hashlib
import json
import math
from pathlib import Path
from typing import Any

import pytest

import rocell.application.adaptive_virtual_session as adaptive_module
from rocell.application.actual_contact_geometry import ActualToolTipContactProjector
from rocell.application.adaptive_virtual_session import (
    ADAPTIVE_VIRTUAL_SESSION_SCHEMA,
    AdaptiveCameraFault,
    AdaptiveCameraFaultSchedule,
    AdaptiveVirtualSessionError,
    AdaptiveVirtualSessionPolicy,
    AdaptiveVirtualSessionReport,
    run_default_adaptive_virtual_session,
)
from rocell.application.board_pose_correction import (
    BoardPoseCorrectionPolicy,
    BoardPoseCorrectionStatus,
)
from rocell.application.virtual_arm_camera import (
    ArmCameraVisionQualityPolicy,
    VirtualArmCameraCaptureMode,
    VirtualArmCameraVisionService,
)
from rocell.geometry import Vec3
from rocell.motion import MotionPhase
from rocell.simulation.virtual_outcome import VirtualTextOutcomeObserver
from rocell.simulation.virtual_workcell import VirtualArmPlant, VirtualFaultScript
from rocell.vision.planar_pose_estimator import PlanarAprilTagBoardPoseEstimator


WORKSPACE = Path(__file__).resolve().parents[3]
COMPLETE_STATUS = "ADAPTIVE_VIRTUAL_SESSION_COMPLETE_WITH_PHYSICAL_HOLDS"


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _mapping_nodes(value: object) -> Iterator[Mapping[str, Any]]:
    """Yield every report mapping so nested authority claims are checked."""

    if isinstance(value, Mapping):
        yield value
        for child in value.values():
            yield from _mapping_nodes(child)
    elif isinstance(value, (list, tuple)):
        for child in value:
            yield from _mapping_nodes(child)


def _nested_values(value: object) -> Iterator[object]:
    yield value
    if isinstance(value, Mapping):
        for child in value.values():
            yield from _nested_values(child)
    elif isinstance(value, (list, tuple)):
        for child in value:
            yield from _nested_values(child)


def _assert_zero_hardware_authority(document: Mapping[str, Any]) -> None:
    for node in _mapping_nodes(document):
        if "simulation_only" in node:
            assert node["simulation_only"] is True
        if "hardware_accessed" in node:
            assert node["hardware_accessed"] is False
        if "hardware_commands_generated" in node:
            assert node["hardware_commands_generated"] == 0
        if "execution_authorized" in node:
            assert node["execution_authorized"] is False
        if "live_motion_authorized" in node:
            assert node["live_motion_authorized"] is False
        if "physical_contact_authorized" in node:
            assert node["physical_contact_authorized"] is False
        if "contact_authorized" in node:
            assert node["contact_authorized"] is False
        if "can_release_physical_gates" in node:
            assert node["can_release_physical_gates"] is False
    authority = document["authority"]
    assert authority["physical_release_effect"] == "NONE"
    assert authority["virtual_commands_executed"] > 0


def _assert_complete(report: AdaptiveVirtualSessionReport) -> None:
    assert report.status == COMPLETE_STATUS
    assert report.pipeline_completed is True
    assert report.fault_reason is None
    assert report.outcome_verified is True
    assert report.ended_at_park is True
    assert report.arm_document["lifecycle"] == "CLOSED"
    lifecycle_history = report.arm_document["lifecycle_history"]
    assert isinstance(lifecycle_history, tuple)
    assert lifecycle_history[-2:] == ("COMPLETE", "CLOSED")
    assert report.executions[-1].executable.phase is MotionPhase.PARK
    assert report.executions[-1].executable.phase_endpoint is True
    assert report.arm_document["last_waypoint_sequence"] == (
        report.executions[-1].executable.execution_sequence
    )
    assert all(attempt.accepted for attempt in report.contact_attempts)


@pytest.fixture(scope="module")
def shifted_keyboard_report() -> AdaptiveVirtualSessionReport:
    return run_default_adaptive_virtual_session(
        WORKSPACE,
        "keyboard",
        "a",
        truth_translation_Wv_mm=Vec3(12.0, 0.0, 0.0),
    )


@pytest.fixture(scope="module")
def shifted_phone_report() -> AdaptiveVirtualSessionReport:
    return run_default_adaptive_virtual_session(
        WORKSPACE,
        "phone",
        "a",
        truth_translation_Wv_mm=Vec3(8.0, 0.0, 0.0),
    )


@pytest.fixture(scope="module")
def zero_offset_reports() -> tuple[
    AdaptiveVirtualSessionReport, AdaptiveVirtualSessionReport
]:
    # A pair gives a full-document deterministic replay assertion without
    # repeating either of the slower corrected-suffix simulations.
    return (
        run_default_adaptive_virtual_session(WORKSPACE, "keyboard", "a"),
        run_default_adaptive_virtual_session(WORKSPACE, "keyboard", "a"),
    )


@pytest.fixture(scope="module")
def correction_limit_report() -> AdaptiveVirtualSessionReport:
    return run_default_adaptive_virtual_session(
        WORKSPACE,
        "keyboard",
        "a",
        truth_translation_Wv_mm=Vec3(12.0, 0.0, 0.0),
        policy=AdaptiveVirtualSessionPolicy(maximum_correction_revisions=0),
    )


@pytest.fixture(scope="module")
def corrected_multi_keyboard_reports() -> tuple[
    AdaptiveVirtualSessionReport, AdaptiveVirtualSessionReport
]:
    def run(text: str) -> AdaptiveVirtualSessionReport:
        return run_default_adaptive_virtual_session(
            WORKSPACE,
            "keyboard",
            text,
            truth_translation_Wv_mm=Vec3(5.0, 0.0, 0.0),
        )

    return run("aa"), run("test")


@pytest.fixture(scope="module")
def corrected_multi_phone_report() -> AdaptiveVirtualSessionReport:
    # The synthetic wide-angle renderer quantizes the most oblique phone-key
    # viewpoints more strongly than the short one-key smoke route.  These are
    # explicit simulation convergence gates, not physical tolerances.
    policy = AdaptiveVirtualSessionPolicy(
        correction_policy=BoardPoseCorrectionPolicy(
            translation_deadband_mm=1.5,
            yaw_deadband_rad=math.radians(0.25),
            tilt_deadband_rad=math.radians(0.25),
        ),
        camera_quality_policy=ArmCameraVisionQualityPolicy(
            maximum_inlier_rmse_px=3.0
        ),
    )
    return run_default_adaptive_virtual_session(
        WORKSPACE,
        "phone",
        "test.",
        truth_translation_Wv_mm=Vec3(5.0, 0.0, 0.0),
        policy=policy,
    )


@pytest.fixture(scope="module")
def scheduled_second_capture_fault_report() -> AdaptiveVirtualSessionReport:
    schedule = AdaptiveCameraFaultSchedule(
        schedule_id="corrected-second-capture-unavailable",
        faults=(
            AdaptiveCameraFault(
                capture_sequence=2,
                capture_mode=VirtualArmCameraCaptureMode.CAMERA_UNAVAILABLE,
            ),
        ),
    )
    return run_default_adaptive_virtual_session(
        WORKSPACE,
        "keyboard",
        "aa",
        truth_translation_Wv_mm=Vec3(5.0, 0.0, 0.0),
        policy=AdaptiveVirtualSessionPolicy(camera_fault_schedule=schedule),
    )


def test_shifted_keyboard_applies_once_then_converges_without_a_second_install(
    shifted_keyboard_report: AdaptiveVirtualSessionReport,
) -> None:
    report = shifted_keyboard_report
    _assert_complete(report)

    assert [
        attempt.decision.status if attempt.decision is not None else None
        for attempt in report.vision_attempts
    ] == [BoardPoseCorrectionStatus.APPLY, BoardPoseCorrectionStatus.NO_CHANGE]
    assert len(report.correction_installations) == 1
    installation = report.correction_installations[0]
    assert report.vision_attempts[0].installation is installation
    assert report.vision_attempts[1].installation is None
    assert installation.suffix.passed
    assert installation.suffix.trajectory_revision == 1
    assert report.final_registration.revision == 1
    assert report.final_registration.registration_hash == (
        installation.suffix.correction_decision.candidate_registration.registration_hash
    )

    first_hover_execution = next(
        index
        for index, record in enumerate(report.executions)
        if record.executable.execution_sequence
        == report.vision_attempts[0].execution_sequence
    )
    assert all(
        record.executable.source_kind == "NOMINAL"
        for record in report.executions[: first_hover_execution + 1]
    )
    assert all(
        record.executable.source_kind == "CORRECTED_SUFFIX"
        for record in report.executions[first_hover_execution + 1 :]
    )
    assert [record.executable.execution_sequence for record in report.executions] == (
        list(range(len(report.executions)))
    )


def test_corrected_truth_contact_is_accepted_and_old_suffix_never_executes(
    shifted_keyboard_report: AdaptiveVirtualSessionReport,
) -> None:
    report = shifted_keyboard_report
    installation = report.correction_installations[0]
    contact = report.contact_attempts[0]

    assert contact.accepted
    assert contact.expected_region_matched
    assert contact.semantic_target == "keyboard:A"
    assert contact.result_document["disposition"] == "ACCEPTED"
    assert contact.result_document["resolved_target_id"] == "keyboard:A"
    assert contact.geometry.truth_registration_sha256 == (
        report.truth_registration_sha256
    )
    assert contact.geometry.to_dict()["planner_board_coordinates_consumed"] is False

    contact_execution = next(
        record
        for record in report.executions
        if record.executable.execution_sequence == contact.execution_sequence
    )
    assert contact_execution.executable.phase is MotionPhase.CONTACT
    assert contact_execution.executable.phase_endpoint
    assert contact_execution.executable.source_kind == "CORRECTED_SUFFIX"
    assert contact_execution.executable.trajectory_revision == 1
    assert contact_execution.executable.registration_sha256 == (
        report.final_registration.registration_hash
    )

    # The entire nominal suffix after the observed hover was hashed before the
    # one queue assignment.  None of those command identities appears in the
    # executed prefix or in the installed corrected suffix.
    executed_hashes = {
        record.executable.executable_hash for record in report.executions
    }
    discarded_hashes = set(installation.discarded_executable_sha256s)
    assert discarded_hashes
    assert executed_hashes.isdisjoint(discarded_hashes)
    final_round = report.nominal_trajectory.final_round
    assert final_round is not None
    observed_source_sequence = report.vision_attempts[0].source_nominal_sequence
    assert observed_source_sequence is not None
    hover_index = next(
        index
        for index, waypoint in enumerate(final_round.waypoints)
        if waypoint.sequence == observed_source_sequence
    )
    assert len(discarded_hashes) == len(final_round.waypoints) - hover_index - 1
    assert any(
        waypoint.phase is MotionPhase.CONTACT
        for waypoint in final_round.waypoints[hover_index + 1 :]
    )
    installation_document = installation.to_dict()
    assert installation_document["old_queue_discarded_atomically"] is True
    assert installation_document["old_joint_results_executable_after_install"] is False


def test_correction_installation_rejects_wrong_suffix_type(
    shifted_keyboard_report: AdaptiveVirtualSessionReport,
) -> None:
    installation = shifted_keyboard_report.correction_installations[0]

    with pytest.raises(TypeError, match="suffix must be CorrectedTrajectorySuffix"):
        replace(installation, suffix=object())  # type: ignore[arg-type]


def test_shifted_phone_uses_truth_contact_and_independent_ui_verification(
    shifted_phone_report: AdaptiveVirtualSessionReport,
) -> None:
    report = shifted_phone_report
    _assert_complete(report)
    assert [
        attempt.decision.status if attempt.decision is not None else None
        for attempt in report.vision_attempts
    ] == [BoardPoseCorrectionStatus.APPLY, BoardPoseCorrectionStatus.NO_CHANGE]
    assert len(report.correction_installations) == 1
    assert [
        (item.action_index, item.required_state, item.passed)
        for item in report.phone_verifications
    ] == [(0, "KEYBOARD_LOWER", True)]

    contact = report.contact_attempts[0]
    assert contact.action_index == 1
    assert contact.semantic_target == "phone:key_a"
    assert contact.accepted
    assert contact.result_document["resolved_target_id"] == "phone:key_a"
    assert contact.geometry.truth_registration_sha256 == report.truth_registration_sha256
    assert report.device_document["schema"] == "rocell.virtual_android.v2"
    assert report.device_document["ui_state"] == "KEYBOARD_LOWER"
    assert report.device_document["last_action_index"] == 1
    # UI-state verification is its own semantic record.  Only the independently
    # resolved achieved-geometry ContactResult reaches the output observer.
    assert report.observer_document["input_contract"] == "CONTACT_RESULT_ONLY"
    assert report.observer_document["action_indices"] == (1,)
    assert report.observer_document["result_count"] == 1
    assert report.observer_document["result_hashes"] == (contact.result_sha256,)
    assert report.device_document["last_contact_result_hash"] == contact.result_sha256
    assert report.device_document["output_sha256"] == _sha256("a")
    assert report.observer_document["output_sha256"] == _sha256("a")


def test_zero_offset_keeps_nominal_registration_and_installs_no_suffix(
    zero_offset_reports: tuple[
        AdaptiveVirtualSessionReport, AdaptiveVirtualSessionReport
    ],
) -> None:
    report, _ = zero_offset_reports
    _assert_complete(report)
    assert len(report.vision_attempts) == 1
    decision = report.vision_attempts[0].decision
    assert decision is not None
    assert decision.status is BoardPoseCorrectionStatus.NO_CHANGE
    assert report.vision_attempts[0].installation is None
    assert report.correction_installations == ()
    assert report.final_registration.registration_hash == (
        report.initial_registration.registration_hash
    )
    assert all(
        record.executable.source_kind == "NOMINAL"
        and record.executable.trajectory_revision == 0
        and record.executable.registration_sha256
        == report.initial_registration.registration_hash
        for record in report.executions
    )
    final_round = report.nominal_trajectory.final_round
    assert final_round is not None
    assert [record.executable.execution_sequence for record in report.executions] == [
        waypoint.sequence for waypoint in final_round.waypoints
    ]


def test_report_is_deterministic_redacted_truth_bound_and_zero_authority(
    zero_offset_reports: tuple[
        AdaptiveVirtualSessionReport, AdaptiveVirtualSessionReport
    ],
) -> None:
    report, replay = zero_offset_reports
    document = report.to_dict()
    replay_document = replay.to_dict()

    assert report.report_hash == replay.report_hash
    assert document == replay_document
    assert document["schema"] == ADAPTIVE_VIRTUAL_SESSION_SCHEMA
    assert document["report_sha256"] == report.report_hash
    assert document["requested_text"] == {
        "sha256": _sha256("a"),
        "normalized_codepoint_length": 1,
        "plaintext_serialized": False,
    }
    assert report.device_document["raw_output_serialized"] is False
    assert report.observer_document["raw_output_serialized"] is False
    assert report.camera_service_document["private_truth_registration_sha256"] == (
        report.truth_registration_sha256
    )
    private_truth = document["private_plant_truth"]
    assert private_truth == {
        "registration_sha256": report.truth_registration_sha256,
        "transform_serialized": False,
        "shared_by_camera_and_contact": True,
    }
    assert all(
        contact.geometry.truth_registration_sha256
        == report.truth_registration_sha256
        for contact in report.contact_attempts
    )
    assert all(not isinstance(value, bytes) for value in _nested_values(document))
    # JSON serialization is itself an important redaction boundary: image bytes
    # and opaque truth objects cannot leak through the public report document.
    serialized = json.dumps(
        document,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    )
    assert '"jpeg_bytes_serialized":false' in serialized
    assert '"synthetic_truth_transform_serialized":false' in serialized
    assert '"raw_output_serialized":false' in serialized
    _assert_zero_hardware_authority(document)

    # Public serialization returns a detached tree, while retained evidence is
    # recursively immutable; neither route can silently change report hashes.
    original_hash = report.report_hash
    camera_document = document["camera_service"]
    assert isinstance(camera_document, dict)
    camera_document["private_truth_registration_sha256"] = "0" * 64
    assert report.report_hash == original_hash
    with pytest.raises(TypeError):
        report.camera_service_document["mutated"] = True  # type: ignore[index]


def test_zero_correction_budget_faults_closed_before_install_or_contact(
    correction_limit_report: AdaptiveVirtualSessionReport,
) -> None:
    report = correction_limit_report
    document = report.to_dict()

    assert report.status == "ADAPTIVE_VIRTUAL_SESSION_FAULTED"
    assert report.pipeline_completed is False
    assert report.fault_reason == "BOARD_POSE_CORRECTION_ITERATION_LIMIT"
    assert report.outcome_verified is False
    assert report.ended_at_park is False
    assert report.arm_document["lifecycle"] == "CLOSED"
    lifecycle_history = report.arm_document["lifecycle_history"]
    assert isinstance(lifecycle_history, tuple)
    assert lifecycle_history[-2:] == ("FAULT", "CLOSED")
    assert len(report.vision_attempts) == 1
    decision = report.vision_attempts[0].decision
    assert decision is not None
    assert decision.status is BoardPoseCorrectionStatus.APPLY
    assert report.vision_attempts[0].installation is None
    assert report.correction_installations == ()
    assert report.contact_attempts == ()
    assert all(
        record.executable.source_kind == "NOMINAL"
        for record in report.executions
    )
    _assert_zero_hardware_authority(document)


def test_default_policy_keeps_legacy_no_fault_document_and_token_binding(
    zero_offset_reports: tuple[
        AdaptiveVirtualSessionReport, AdaptiveVirtualSessionReport
    ],
) -> None:
    report, _ = zero_offset_reports
    policy_document = report.policy.to_dict()

    assert "camera_fault_schedule" not in policy_document
    assert "camera_quality_policy" not in policy_document
    assert "camera_fault_consumption" not in report.to_dict()
    assert report.consumed_camera_faults == ()
    assert report.token.fault_script_hash == (
        VirtualFaultScript("adaptive-none").definition_hash
    )
    assert all(
        attempt.result.capture_mode is VirtualArmCameraCaptureMode.NORMAL
        for attempt in report.vision_attempts
    )


def test_camera_fault_schedule_is_bounded_canonical_and_non_normal() -> None:
    with pytest.raises(AdaptiveVirtualSessionError, match="must be non-normal"):
        AdaptiveCameraFault(1, VirtualArmCameraCaptureMode.NORMAL)

    duplicate_sequence = (
        AdaptiveCameraFault(1, VirtualArmCameraCaptureMode.TAG_LOSS),
        AdaptiveCameraFault(1, VirtualArmCameraCaptureMode.EXCESS_BLUR),
    )
    with pytest.raises(AdaptiveVirtualSessionError, match="must be unique"):
        AdaptiveCameraFaultSchedule("duplicate", duplicate_sequence)

    late_fault = AdaptiveCameraFaultSchedule(
        "outside-policy-capture-budget",
        (AdaptiveCameraFault(2, VirtualArmCameraCaptureMode.STALE_FRAME),),
    )
    with pytest.raises(
        AdaptiveVirtualSessionError, match="exceeds maximum_camera_captures"
    ):
        AdaptiveVirtualSessionPolicy(
            camera_fault_schedule=late_fault,
            maximum_camera_captures=1,
        )


def test_scheduled_moving_camera_fault_is_consumed_once_after_atomic_replan(
    scheduled_second_capture_fault_report: AdaptiveVirtualSessionReport,
) -> None:
    report = scheduled_second_capture_fault_report
    schedule = report.policy.camera_fault_schedule

    assert report.status == "ADAPTIVE_VIRTUAL_SESSION_FAULTED"
    assert report.fault_reason == "ARM_CAMERA_UNAVAILABLE"
    assert report.arm_document["lifecycle"] == "CLOSED"
    lifecycle_history = report.arm_document["lifecycle_history"]
    assert isinstance(lifecycle_history, tuple)
    assert lifecycle_history[-2:] == ("FAULT", "CLOSED")
    assert len(report.correction_installations) == 1
    assert report.contact_attempts == ()
    assert report.consumed_camera_faults == schedule.faults
    assert len({item.fault_hash for item in report.consumed_camera_faults}) == 1
    assert report.token.fault_script_hash == schedule.definition_hash
    assert [item.result.capture_mode for item in report.vision_attempts] == [
        VirtualArmCameraCaptureMode.NORMAL,
        VirtualArmCameraCaptureMode.CAMERA_UNAVAILABLE,
    ]
    assert [item.result.capture_sequence for item in report.vision_attempts] == [1, 2]

    failed_attempt = report.vision_attempts[-1]
    final_execution = report.executions[-1].executable
    assert final_execution.execution_sequence == failed_attempt.execution_sequence
    assert final_execution.phase is MotionPhase.HOVER
    assert final_execution.phase_endpoint is True
    assert final_execution.action_index == 0
    assert final_execution.source_kind == "CORRECTED_SUFFIX"
    assert final_execution.trajectory_revision == 1

    installation = report.correction_installations[0]
    assert {
        item.executable.executable_hash for item in report.executions
    }.isdisjoint(installation.discarded_executable_sha256s)
    consumption = report.to_dict()["camera_fault_consumption"]
    assert isinstance(consumption, dict)
    assert consumption["consumed_fault_sha256s"] == [
        schedule.faults[0].fault_hash
    ]
    assert consumption["unconsumed_fault_sha256s"] == []
    assert consumption["each_fault_consumed_at_most_once"] is True


@pytest.mark.parametrize(
    "capture_mode",
    (
        VirtualArmCameraCaptureMode.CAMERA_UNAVAILABLE,
        VirtualArmCameraCaptureMode.TAG_LOSS,
        VirtualArmCameraCaptureMode.EXCESS_BLUR,
        VirtualArmCameraCaptureMode.EXCESS_NOISE,
        VirtualArmCameraCaptureMode.UNQUALIFIED_TIMESTAMP,
        VirtualArmCameraCaptureMode.STALE_FRAME,
    ),
)
def test_every_moving_camera_fault_mode_fails_before_contact_and_closes(
    capture_mode: VirtualArmCameraCaptureMode,
) -> None:
    """Exercise the schedule at the adaptive boundary, not just camera unit level."""

    scheduled = AdaptiveCameraFault(1, capture_mode)
    report = run_default_adaptive_virtual_session(
        WORKSPACE,
        "keyboard",
        "a",
        policy=AdaptiveVirtualSessionPolicy(
            camera_fault_schedule=AdaptiveCameraFaultSchedule(
                f"first-capture-{capture_mode.value.lower()}",
                (scheduled,),
            )
        ),
    )

    assert report.status == "ADAPTIVE_VIRTUAL_SESSION_FAULTED"
    assert report.pipeline_completed is False
    assert report.outcome_verified is False
    assert report.ended_at_park is False
    assert report.contact_attempts == ()
    assert report.consumed_camera_faults == (scheduled,)
    assert len(report.vision_attempts) == 1
    assert report.vision_attempts[0].result.capture_mode is capture_mode
    assert report.vision_attempts[0].result.passed is False
    assert report.arm_document["lifecycle"] == "CLOSED"
    lifecycle_history = report.arm_document["lifecycle_history"]
    assert isinstance(lifecycle_history, tuple)
    assert lifecycle_history[-2:] == ("FAULT", "CLOSED")
    _assert_zero_hardware_authority(report.to_dict())


@pytest.mark.parametrize(
    (
        "expected_boundary",
        "owner",
        "attribute",
        "last_phase",
        "recorded_contact_count",
    ),
    (
        ("ARM_EXECUTE_WAYPOINT", VirtualArmPlant, "execute_waypoint", None, 0),
        (
            "ARM_CAMERA_PROCESS",
            VirtualArmCameraVisionService,
            "process",
            MotionPhase.HOVER,
            0,
        ),
        (
            "ARM_CAMERA_PROCESS",
            PlanarAprilTagBoardPoseEstimator,
            "estimate",
            MotionPhase.HOVER,
            0,
        ),
        (
            "BOARD_POSE_CORRECTION",
            adaptive_module,
            "decide_board_pose_correction",
            MotionPhase.HOVER,
            0,
        ),
        (
            "CONTACT_GEOMETRY",
            ActualToolTipContactProjector,
            "project",
            MotionPhase.CONTACT,
            0,
        ),
        (
            "OUTCOME_OBSERVER_CONSUME",
            VirtualTextOutcomeObserver,
            "consume",
            MotionPhase.CONTACT,
            1,
        ),
    ),
    ids=("arm", "camera", "estimator", "correction", "contact", "observer"),
)
def test_unexpected_boundary_exceptions_fault_close_and_halt_queue(
    monkeypatch: pytest.MonkeyPatch,
    expected_boundary: str,
    owner: Any,
    attribute: str,
    last_phase: MotionPhase | None,
    recorded_contact_count: int,
) -> None:
    calls = 0

    def explode(*args: object, **kwargs: object) -> None:
        nonlocal calls
        calls += 1
        raise RuntimeError("untrusted dependency detail must not be serialized")

    monkeypatch.setattr(owner, attribute, explode)
    report = run_default_adaptive_virtual_session(WORKSPACE, "keyboard", "aa")

    assert calls == 1
    assert report.status == "ADAPTIVE_VIRTUAL_SESSION_FAULTED"
    assert report.fault_reason == f"ADAPTIVE_UNEXPECTED_FAILURE:{expected_boundary}"
    assert "untrusted" not in json.dumps(report.to_dict())
    assert report.arm_document["lifecycle"] == "CLOSED"
    lifecycle_history = report.arm_document["lifecycle_history"]
    assert isinstance(lifecycle_history, tuple)
    assert lifecycle_history[-2:] == ("FAULT", "CLOSED")
    assert "COMPLETE" not in lifecycle_history
    assert len(report.contact_attempts) == recorded_contact_count
    assert all(item.action_index == 0 for item in report.contact_attempts)
    if expected_boundary == "OUTCOME_OBSERVER_CONSUME":
        assert report.contact_attempts[0].accepted
        assert report.observer_document["result_count"] == 0
    assert report.outcome_verified is False
    assert report.ended_at_park is False
    assert report.arm_document["virtual_commands_executed"] == len(
        report.executions
    )
    if last_phase is None:
        assert report.executions == ()
        assert report.arm_document["last_waypoint_sequence"] is None
    else:
        final_execution = report.executions[-1].executable
        assert final_execution.phase is last_phase
        assert final_execution.phase_endpoint is True
        assert report.arm_document["last_waypoint_sequence"] == (
            final_execution.execution_sequence
        )


def _assert_corrected_multi_action_correlation(
    report: AdaptiveVirtualSessionReport,
    *,
    expected_action_indices: tuple[int, ...],
    expected_targets: tuple[str, ...],
) -> None:
    _assert_complete(report)
    assert len(report.correction_installations) == 1
    assert report.final_registration.revision == 1
    assert [
        attempt.decision.status if attempt.decision is not None else None
        for attempt in report.vision_attempts
    ] == [BoardPoseCorrectionStatus.APPLY] + [
        BoardPoseCorrectionStatus.NO_CHANGE
    ] * len(expected_action_indices)
    assert [item.action_index for item in report.vision_attempts] == [
        expected_action_indices[0],
        *expected_action_indices,
    ]
    assert tuple(item.action_index for item in report.contact_attempts) == (
        expected_action_indices
    )
    assert tuple(item.semantic_target for item in report.contact_attempts) == (
        expected_targets
    )
    assert report.observer_document["action_indices"] == expected_action_indices

    executions = {
        item.executable.execution_sequence: item.executable
        for item in report.executions
    }
    for contact in report.contact_attempts:
        executable = executions[contact.execution_sequence]
        assert executable.phase is MotionPhase.CONTACT
        assert executable.phase_endpoint is True
        assert executable.action_index == contact.action_index
        assert executable.semantic_target == contact.semantic_target
        assert executable.source_kind == "CORRECTED_SUFFIX"
        assert executable.trajectory_revision == 1
        assert contact.geometry.joint_sequence == executable.execution_sequence

    installation = report.correction_installations[0]
    executed_hashes = {
        item.executable.executable_hash for item in report.executions
    }
    assert executed_hashes.isdisjoint(installation.discarded_executable_sha256s)
    first_observed_sequence = report.vision_attempts[0].execution_sequence
    first_observed_index = next(
        index
        for index, item in enumerate(report.executions)
        if item.executable.execution_sequence == first_observed_sequence
    )
    assert all(
        item.executable.source_kind == "CORRECTED_SUFFIX"
        for item in report.executions[first_observed_index + 1 :]
    )


def test_corrected_multi_character_keyboard_missions_replace_suffix_atomically(
    corrected_multi_keyboard_reports: tuple[
        AdaptiveVirtualSessionReport, AdaptiveVirtualSessionReport
    ],
) -> None:
    aa_report, test_report = corrected_multi_keyboard_reports
    _assert_corrected_multi_action_correlation(
        aa_report,
        expected_action_indices=(0, 1),
        expected_targets=("keyboard:A", "keyboard:A"),
    )
    _assert_corrected_multi_action_correlation(
        test_report,
        expected_action_indices=(0, 1, 2, 3),
        expected_targets=(
            "keyboard:T",
            "keyboard:E",
            "keyboard:S",
            "keyboard:T",
        ),
    )


def test_corrected_phone_test_period_mission_preserves_action_correlation(
    corrected_multi_phone_report: AdaptiveVirtualSessionReport,
) -> None:
    report = corrected_multi_phone_report
    _assert_corrected_multi_action_correlation(
        report,
        expected_action_indices=(1, 2, 3, 4, 5),
        expected_targets=(
            "phone:key_t",
            "phone:key_e",
            "phone:key_s",
            "phone:key_t",
            "phone:key_period",
        ),
    )
    assert [
        (item.action_index, item.required_state, item.passed)
        for item in report.phone_verifications
    ] == [(0, "KEYBOARD_LOWER", True)]
    assert report.policy.camera_quality_policy is not None
    assert (
        report.camera_service_document["quality_policy_sha256"]
        == report.policy.camera_quality_policy.content_hash
    )
