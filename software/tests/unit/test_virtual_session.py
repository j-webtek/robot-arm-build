from __future__ import annotations

from collections.abc import Iterator, Mapping
import hashlib
from pathlib import Path
from typing import Any

import pytest

from rocell.application.virtual_session import (
    VirtualSessionError,
    VirtualSessionLifecycle,
    VirtualSessionReport,
    run_default_virtual_session,
)
from rocell.motion import MotionPhase
from rocell.simulation.virtual_workcell import (
    VirtualFaultKind,
    VirtualFaultScript,
    VirtualFaultTrigger,
)


WORKSPACE = Path(__file__).resolve().parents[3]


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _mapping_nodes(value: object) -> Iterator[Mapping[str, Any]]:
    """Yield every mapping so nested authority claims cannot escape checks."""

    if isinstance(value, Mapping):
        yield value
        for child in value.values():
            yield from _mapping_nodes(child)
    elif isinstance(value, (list, tuple)):
        for child in value:
            yield from _mapping_nodes(child)


def _string_values(value: object) -> Iterator[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, Mapping):
        for child in value.values():
            yield from _string_values(child)
    elif isinstance(value, (list, tuple)):
        for child in value:
            yield from _string_values(child)


def _assert_zero_hardware_authority(document: Mapping[str, Any]) -> None:
    for node in _mapping_nodes(document):
        if "hardware_accessed" in node:
            assert node["hardware_accessed"] is False
        if "hardware_commands_generated" in node:
            assert node["hardware_commands_generated"] == 0
        if "execution_authorized" in node:
            assert node["execution_authorized"] is False
        if "live_motion_authorized" in node:
            assert node["live_motion_authorized"] is False
        if "contact_authorized" in node:
            assert node["contact_authorized"] is False
        if "can_release_physical_gates" in node:
            assert node["can_release_physical_gates"] is False
    authority = document["authority"]
    assert authority["simulation_only"] is True
    assert authority["physical_release_effect"] == "NONE"
    assert authority["virtual_commands_executed"] > 0


def _assert_hash_only_output(report: VirtualSessionReport, text: str) -> None:
    document = report.to_dict()
    digest = _sha256(text)
    assert document["requested_text"] == {
        "sha256": digest,
        "normalized_codepoint_length": len(text),
        "plaintext_serialized": False,
    }
    assert document["outcome"] == {
        "expected_sha256": digest,
        "expected_length": len(text),
        "observed_sha256": digest,
        "observed_length": len(text),
        "matches": True,
        "raw_output_serialized": False,
    }
    assert report.device_document["output_sha256"] == digest
    assert report.device_document["output_length"] == len(text)
    assert report.device_document["raw_output_serialized"] is False
    assert report.observer_document["output_sha256"] == digest
    assert report.observer_document["output_length"] == len(text)
    assert report.observer_document["raw_output_serialized"] is False
    assert report.observer_document["input_contract"] == "CONTACT_RESULT_ONLY"
    assert report.observer_document["result_hashes"][-1] == (
        report.device_document["last_contact_result_hash"]
    )
    # Semantic target names remain intentionally visible for action correlation,
    # but the complete user text must never be stored as a report value.
    assert text not in tuple(_string_values(document))


def _assert_successfully_parked_and_closed(report: VirtualSessionReport) -> None:
    assert report.pipeline_completed is True
    assert report.outcome_verified is True
    assert report.ended_at_park is True
    assert report.fault_reason is None
    assert report.lifecycle_history[-3:] == (
        VirtualSessionLifecycle.OUTCOME_VERIFIED,
        VirtualSessionLifecycle.RETURNED_TO_PARK,
        VirtualSessionLifecycle.CLOSED_COMPLETE,
    )
    final_round = report.trajectory.final_round
    assert final_round is not None
    assert final_round.waypoints[-1].phase is MotionPhase.PARK
    assert final_round.waypoints[-1].phase_endpoint is True
    assert report.arm_document["last_waypoint_sequence"] == final_round.waypoints[-1].sequence
    assert report.arm_document["lifecycle"] == "CLOSED"
    assert report.arm_document["lifecycle_history"][-2:] == ["COMPLETE", "CLOSED"]
    assert report.ledger.sealed is True
    assert report.pixel_vision_completed is True
    assert report.vision_document["sealed"] is True
    assert report.vision_document["all_attempts_passed"] is True
    assert report.vision_document["robot_frame_correction_applied"] is False


@pytest.fixture(scope="module")
def keyboard_report() -> VirtualSessionReport:
    return run_default_virtual_session(WORKSPACE, "keyboard", "test")


@pytest.fixture(scope="module")
def phone_report() -> VirtualSessionReport:
    return run_default_virtual_session(WORKSPACE, "phone", "test.")


@pytest.fixture(scope="module")
def duplicate_report() -> VirtualSessionReport:
    return run_default_virtual_session(WORKSPACE, "keyboard", "aa")


def test_golden_keyboard_test_is_hash_verified_parked_and_zero_authority(
    keyboard_report: VirtualSessionReport,
) -> None:
    document = keyboard_report.to_dict()
    assert keyboard_report.status == (
        "VIRTUAL_SESSION_COMPLETE_WITH_MODEL_AND_PHYSICAL_HOLDS"
    )
    assert keyboard_report.device_document["accepted_contact_count"] == 4
    assert keyboard_report.device_document["schema"] == "rocell.virtual_keyboard.v2"
    assert keyboard_report.device_document["contact_input_contract"] == (
        "ACHIEVED_BOARD_XYZ_NORMAL_DWELL_ONLY"
    )
    assert keyboard_report.observer_document["result_count"] == 4
    assert keyboard_report.device_document["last_action_index"] == 3
    assert document["virtual_model_complete"] is False
    assert document["schema"] == "rocell.virtual_session_report.v3"
    assert document["pixel_vision"]["attempt_count"] == 4
    assert document["pixel_vision"]["passed_attempt_count"] == 4
    _assert_hash_only_output(keyboard_report, "test")
    _assert_successfully_parked_and_closed(keyboard_report)
    _assert_zero_hardware_authority(document)


def test_golden_android_test_period_enforces_ui_state_and_hash_only_output(
    phone_report: VirtualSessionReport,
) -> None:
    document = phone_report.to_dict()
    assert phone_report.device_document["schema"] == "rocell.virtual_android.v2"
    assert phone_report.device_document["ui_state"] == "KEYBOARD_LOWER"
    assert phone_report.device_document["accepted_contact_count"] == 5
    assert phone_report.device_document["last_action_index"] == 5
    assert phone_report.observer_document["action_indices"] == [1, 2, 3, 4, 5]
    assert phone_report.vision_document["attempt_count"] == 5
    assert [
        attempt["action_index"] for attempt in phone_report.vision_document["attempts"]
    ] == [1, 2, 3, 4, 5]
    contacts = [event for event in phone_report.ledger.events if event.operation == "contact"]
    assert [(event.action_index, event.target_id) for event in contacts] == [
        (1, "phone:key_t"),
        (2, "phone:key_e"),
        (3, "phone:key_s"),
        (4, "phone:key_t"),
        (5, "phone:key_period"),
    ]
    verifications = [
        event for event in phone_report.ledger.events if event.operation == "verify_state"
    ]
    assert [(event.action_index, event.status) for event in verifications] == [(0, "PASS")]
    _assert_hash_only_output(phone_report, "test.")
    _assert_successfully_parked_and_closed(phone_report)
    _assert_zero_hardware_authority(document)


def test_duplicate_keyboard_targets_retain_distinct_action_indices(
    duplicate_report: VirtualSessionReport,
) -> None:
    contacts = [
        event for event in duplicate_report.ledger.events if event.operation == "contact"
    ]
    assert [(event.action_index, event.target_id) for event in contacts] == [
        (0, "keyboard:A"),
        (1, "keyboard:A"),
    ]
    assert contacts[0].waypoint_sequence != contacts[1].waypoint_sequence
    final_round = duplicate_report.trajectory.final_round
    assert final_round is not None
    contact_endpoints = [
        waypoint
        for waypoint in final_round.waypoints
        if waypoint.phase is MotionPhase.CONTACT and waypoint.phase_endpoint
    ]
    assert [(waypoint.action_index, waypoint.semantic_target) for waypoint in contact_endpoints] == [
        (0, "keyboard:A"),
        (1, "keyboard:A"),
    ]
    result_by_sequence = {
        result.waypoint_sequence: result for result in final_round.joint_results
    }
    assert [
        result_by_sequence[waypoint.sequence].action_index for waypoint in contact_endpoints
    ] == [0, 1]
    _assert_hash_only_output(duplicate_report, "aa")
    _assert_successfully_parked_and_closed(duplicate_report)


def test_injected_keyboard_missed_contact_fails_stops_and_closes() -> None:
    trigger = VirtualFaultTrigger(
        "miss-first-a",
        VirtualFaultKind.KEYBOARD_MISSED_CONTACT,
        "keyboard",
        "contact",
        occurrence=1,
        action_index=0,
        target_id="keyboard:A",
    )
    report = run_default_virtual_session(
        WORKSPACE,
        "keyboard",
        "a",
        fault_script=VirtualFaultScript("missed-contact", (trigger,)),
    )

    assert report.status == "VIRTUAL_SESSION_FAULTED"
    assert report.pipeline_completed is False
    assert report.outcome_verified is False
    assert report.ended_at_park is False
    assert report.fault_reason == VirtualFaultKind.KEYBOARD_MISSED_CONTACT.value
    assert report.lifecycle_history[-2:] == (
        VirtualSessionLifecycle.FAULTED,
        VirtualSessionLifecycle.CLOSED,
    )
    assert report.arm_document["lifecycle"] == "CLOSED"
    assert report.arm_document["lifecycle_history"][-2:] == ["FAULT", "CLOSED"]
    assert report.device_document["output_sha256"] == _sha256("")
    assert report.device_document["output_length"] == 0
    assert report.observer_document["result_count"] == 1
    assert report.observer_document["dispositions"] == ["MISSED_CONTACT"]
    assert report.final_fault_script.consumed_trigger_ids == frozenset({trigger.trigger_id})
    fault_contacts = [
        event
        for event in report.ledger.events
        if event.component == "keyboard" and event.status == "FAULT"
    ]
    assert len(fault_contacts) == 1
    assert (
        fault_contacts[0].action_index,
        fault_contacts[0].target_id,
        fault_contacts[0].fault_trigger_id,
    ) == (0, "keyboard:A", trigger.trigger_id)
    assert report.ledger.sealed is True
    _assert_zero_hardware_authority(report.to_dict())


def test_valid_but_unused_fault_selector_is_rejected() -> None:
    unused = VirtualFaultTrigger(
        "second-contact-never-occurs",
        VirtualFaultKind.KEYBOARD_MISSED_CONTACT,
        "keyboard",
        "contact",
        occurrence=2,
        action_index=0,
        target_id="keyboard:A",
    )
    with pytest.raises(
        VirtualSessionError,
        match="fault trigger did not match exactly once: second-contact-never-occurs",
    ):
        run_default_virtual_session(
            WORKSPACE,
            "keyboard",
            "a",
            fault_script=VirtualFaultScript("unused-selector", (unused,)),
        )


def test_fault_kind_and_component_mismatch_is_rejected_before_planning() -> None:
    mismatched = VirtualFaultTrigger(
        "invalid-routing",
        VirtualFaultKind.KEYBOARD_MISSED_CONTACT,
        "arm",
        "execute_waypoint",
    )
    with pytest.raises(
        VirtualSessionError,
        match="fault KEYBOARD_MISSED_CONTACT cannot target arm/execute_waypoint",
    ):
        run_default_virtual_session(
            WORKSPACE,
            "keyboard",
            "a",
            fault_script=VirtualFaultScript("invalid-routing", (mismatched,)),
        )


@pytest.mark.parametrize(
    (
        "kind",
        "expected_capture_mode",
        "expected_stage",
        "frame_present",
        "accepted_ids",
    ),
    (
        (
            VirtualFaultKind.CAMERA_UNAVAILABLE,
            "CAMERA_UNAVAILABLE",
            "CAPTURE",
            False,
            None,
        ),
        (VirtualFaultKind.CAMERA_TAG_LOSS, "TAG_LOSS", "POSE", True, [4, 5]),
    ),
)
def test_camera_faults_flow_through_pixel_evidence_and_fail_stop(
    kind: VirtualFaultKind,
    expected_capture_mode: str,
    expected_stage: str,
    frame_present: bool,
    accepted_ids: list[int] | None,
) -> None:
    trigger = VirtualFaultTrigger(
        f"first-{kind.value.lower()}",
        kind,
        "camera",
        "observe",
        occurrence=1,
        action_index=0,
        target_id="keyboard:A",
    )
    report = run_default_virtual_session(
        WORKSPACE,
        "keyboard",
        "a",
        fault_script=VirtualFaultScript("camera-fault", (trigger,)),
    )

    assert report.status == "VIRTUAL_SESSION_FAULTED"
    assert report.fault_reason == kind.value
    assert report.vision_document["sealed"] is True
    assert report.vision_document["attempt_count"] == 1
    assert report.vision_document["passed_attempt_count"] == 0
    result = report.vision_document["attempts"][0]["result"]
    assert result["capture_mode"] == expected_capture_mode
    assert result["stage"] == expected_stage
    assert (result["frame"] is not None) is frame_present
    if accepted_ids is None:
        assert result["detection_batch"] is None
    else:
        assert [
            detection["tag"]["id"]
            for detection in result["detection_batch"]["detections"]
            if detection["detector_accepted"]
        ] == accepted_ids
    assert report.arm_document["lifecycle"] == "CLOSED"
    assert report.lifecycle_history[-2:] == (
        VirtualSessionLifecycle.FAULTED,
        VirtualSessionLifecycle.CLOSED,
    )
