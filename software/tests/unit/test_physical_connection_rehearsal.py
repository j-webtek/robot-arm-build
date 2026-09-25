from __future__ import annotations

from dataclasses import replace
import hashlib
import inspect
import json

import pytest

from rocell.application.physical_connection_contracts import (
    FAKE_PROVIDER_DESCRIPTOR,
)
from rocell.application.physical_connection_rehearsal import (
    DEFAULT_REHEARSAL_RUN_ID,
    PHYSICAL_CONNECTION_REHEARSAL_SCHEMA,
    REHEARSAL_CONTRACT_SHA256,
    REHEARSAL_STEP_EVIDENCE_SCHEMA,
    PhysicalConnectionRehearsalError,
    RehearsalFault,
    RehearsalOutcome,
    RehearsalStepOutcome,
    run_physical_connection_rehearsal,
)


NOMINAL_STEPS = (
    "host_dependencies",
    "camera_discovery",
    "camera_open",
    "camera_configuration",
    "camera_flush",
    "camera_fresh_frame",
    "camera_close_reopen",
    "camera_final_close",
    "arm_unpowered_identity",
    "arm_single_t105",
)

EXPECTED_BLOCK_STEP = {
    RehearsalFault.WRONG_CAMERA_IDENTITY: "camera_discovery",
    RehearsalFault.WRONG_CAMERA_MODE: "camera_configuration",
    RehearsalFault.STALE_CAMERA_FRAME: "camera_fresh_frame",
    RehearsalFault.CAMERA_IDENTITY_DRIFT: "camera_close_reopen",
    RehearsalFault.CAMERA_CLOSE_FAILURE: "camera_final_close",
    RehearsalFault.WRONG_ARM_IDENTITY: "arm_unpowered_identity",
    RehearsalFault.DIRTY_ARM_BUFFER: "arm_single_t105",
    RehearsalFault.MALFORMED_T1051_RESPONSE: "arm_single_t105",
    RehearsalFault.RETRY_PROHIBITION: "arm_retry_prohibition",
}


def _step_payload(report: object, step_id: str) -> dict[str, object]:
    steps = getattr(report, "steps")
    step = next(item for item in steps if item.step_id == step_id)
    decoded = json.loads(step.evidence_canonical_json)
    assert isinstance(decoded, dict)
    payload = decoded["payload"]
    assert isinstance(payload, dict)
    return payload


def _assert_zero_physical_authority(report: object) -> None:
    content = getattr(report, "to_dict")()
    assert content["physical_effects"] == {
        "camera_open_count": 0,
        "camera_frame_count": 0,
        "serial_open_count": 0,
        "serial_write_count": 0,
        "power_event_count": 0,
        "t104_command_count": 0,
        "motion_command_count": 0,
        "contact_command_count": 0,
        "torque_command_count": 0,
    }
    assert content["authority"] == {
        "hardware_presence": False,
        "live_capture": False,
        "feedback_connection": False,
        "robot_motion": False,
        "contact": False,
        "physical_qualification": False,
    }
    assert content["simulation_only"] is True
    assert content["hardware_accessed"] is False
    assert content["safety_invariants"] == {
        "all_physical_effects_zero": True,
        "no_t104_motion_contact_or_torque": True,
        "no_retry_write": True,
    }


def test_nominal_rehearsal_executes_the_exact_ordered_lifecycle() -> None:
    report = run_physical_connection_rehearsal()

    assert report.schema == PHYSICAL_CONNECTION_REHEARSAL_SCHEMA
    assert report.run_id == DEFAULT_REHEARSAL_RUN_ID
    assert report.fault is RehearsalFault.NONE
    assert report.outcome is RehearsalOutcome.COMPLETE_SYNTHETIC
    assert report.rehearsal_passed is True
    assert report.expected_fault_blocked is False
    assert tuple(step.step_id for step in report.steps) == NOMINAL_STEPS
    assert tuple(step.sequence for step in report.steps) == tuple(range(1, 11))
    assert all(step.outcome is RehearsalStepOutcome.PASS for step in report.steps)
    assert report.simulated_effects.to_dict() == {
        "camera_open_calls": 2,
        "camera_capture_calls": 1,
        "retained_camera_frames": 1,
        "arm_identity_inspections": 1,
        "t105_provider_calls": 1,
        "t105_wire_attempts": 1,
        "retry_writes": 0,
    }
    _assert_zero_physical_authority(report)


def test_nominal_camera_evidence_binds_exact_identity_mode_freshness_and_close() -> None:
    report = run_physical_connection_rehearsal()
    discovery = _step_payload(report, "camera_discovery")
    configuration = _step_payload(report, "camera_configuration")
    flush = _step_payload(report, "camera_flush")
    frame = _step_payload(report, "camera_fresh_frame")
    reopen = _step_payload(report, "camera_close_reopen")
    final_close = _step_payload(report, "camera_final_close")

    devices = discovery["devices"]
    assert isinstance(devices, list) and len(devices) == 1
    assert devices[0]["manufacturer"] == "Arducam"
    assert devices[0]["model"] == "B0477"
    assert devices[0]["sensor"] == "Sony IMX283"
    assert discovery["ordinal_fallback_used"] is False
    assert configuration["observed"]["mode"] == {
        "width_px": 5472,
        "height_px": 3648,
        "fps_numerator": 9,
        "fps_denominator": 1,
        "fourcc": "YUY2",
        "host_bus": "USB_3_X",
    }
    assert configuration["observed"]["controls"]["exposure_mode"] == "MANUAL"
    assert configuration["fallback_negotiated"] is False
    assert flush["buffer_empty_after"] is True
    assert frame["receipt"]["sequence"] > flush["last_discarded_sequence"]
    assert frame["receipt"]["configuration_sha256"] == configuration[
        "requested_configuration_sha256"
    ]
    assert frame["payload_sha256"] == frame["receipt"]["payload_sha256"]
    assert reopen["close_receipt"]["close_succeeded"] is True
    assert reopen["previous_session_id"] != reopen["reopened_session"]["session_id"]
    assert reopen["reopened_identity"]["unit_serial"] == devices[0]["unit_serial"]
    assert reopen["configuration_readback"]["observed"] == configuration["observed"]
    assert final_close["close_attempted"] is True
    assert final_close["close_succeeded"] is True
    assert final_close["was_already_closed"] is False


def test_nominal_arm_evidence_is_one_t105_t1051_and_never_motion() -> None:
    report = run_physical_connection_rehearsal()
    identity = _step_payload(report, "arm_unpowered_identity")
    feedback = _step_payload(report, "arm_single_t105")

    assert identity["serial_port_opened"] is False
    assert identity["bytes_read"] == 0
    assert identity["bytes_written"] == 0
    assert identity["observed_identity"]["baudrate"] == 115200
    assert identity["observed_identity"]["rts"] is False
    assert identity["observed_identity"]["dtr"] is False
    assert bytes.fromhex(feedback["request_bytes_hex"]) == b'{"T":105}\n'
    response = bytes.fromhex(feedback["response_bytes_hex"])
    assert json.loads(response)["T"] == 1051
    assert feedback["write_attempts"] == 1
    assert feedback["feedback_query_count"] == 1
    assert feedback["retry_count"] == 0
    assert feedback["t104_motion_count"] == 0
    assert feedback["connection_closed"] is True
    assert report.t104_command_count == 0
    assert report.motion_command_count == 0
    assert report.contact_command_count == 0


def test_report_is_byte_deterministic_canonical_and_explicitly_hash_bound() -> None:
    first = run_physical_connection_rehearsal(run_id="repeatable-run")
    second = run_physical_connection_rehearsal(run_id="repeatable-run")

    assert first.canonical_json == second.canonical_json
    assert first.report_sha256 == second.report_sha256
    assert first.report_sha256 == hashlib.sha256(
        first.canonical_json.encode("utf-8")
    ).hexdigest()
    assert json.dumps(
        json.loads(first.canonical_json),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ) == first.canonical_json
    assert first.contract_sha256 == REHEARSAL_CONTRACT_SHA256
    assert tuple(role for role, _digest in first.provider_role_hashes) == (
        "arm",
        "camera",
        "host",
    )
    assert all(
        digest == FAKE_PROVIDER_DESCRIPTOR.descriptor_sha256
        for _role, digest in first.provider_role_hashes
    )
    serialized_hashes = first.to_dict()["evidence_hashes"]
    assert serialized_hashes == [
        {
            "sequence": step.sequence,
            "step_id": step.step_id,
            "evidence_sha256": step.evidence_sha256,
        }
        for step in first.steps
    ]
    for step in first.steps:
        assert step.provider_descriptor_sha256 == (
            FAKE_PROVIDER_DESCRIPTOR.descriptor_sha256
        )
        assert step.evidence_sha256 == hashlib.sha256(
            step.evidence_canonical_json.encode("utf-8")
        ).hexdigest()
        assert json.loads(step.evidence_canonical_json)["schema"] == (
            REHEARSAL_STEP_EVIDENCE_SCHEMA
        )


@pytest.mark.parametrize(
    "fault, expected_step",
    tuple(EXPECTED_BLOCK_STEP.items()),
)
def test_each_deterministic_fault_fails_closed_at_the_intended_step(
    fault: RehearsalFault,
    expected_step: str,
) -> None:
    report = run_physical_connection_rehearsal(fault=fault)
    blocked = tuple(
        step
        for step in report.steps
        if step.outcome is RehearsalStepOutcome.BLOCKED_EXPECTED
    )

    assert report.fault is fault
    assert report.outcome is RehearsalOutcome.EXPECTED_FAULT_BLOCKED
    assert report.rehearsal_passed is False
    assert report.expected_fault_blocked is True
    assert len(blocked) == 1
    assert blocked[0].step_id == expected_step
    _assert_zero_physical_authority(report)


def test_camera_faults_retain_specific_mode_freshness_drift_and_close_evidence() -> None:
    wrong_mode = run_physical_connection_rehearsal(
        fault=RehearsalFault.WRONG_CAMERA_MODE
    )
    stale = run_physical_connection_rehearsal(
        fault=RehearsalFault.STALE_CAMERA_FRAME
    )
    drift = run_physical_connection_rehearsal(
        fault=RehearsalFault.CAMERA_IDENTITY_DRIFT
    )
    close = run_physical_connection_rehearsal(
        fault=RehearsalFault.CAMERA_CLOSE_FAILURE
    )

    assert "5472x3648@9 YUY2" in _step_payload(
        wrong_mode, "camera_configuration"
    )["message"]
    assert "latency" in _step_payload(stale, "camera_fresh_frame")["message"]
    assert "identity drifted" in _step_payload(
        drift, "camera_close_reopen"
    )["message"]
    close_payload = _step_payload(close, "camera_final_close")
    assert close_payload["close_attempted"] is True
    assert close_payload["close_succeeded"] is False
    assert close_payload["failure_code"] == "DETERMINISTIC_FINAL_CLOSE_FAILURE"
    for report in (wrong_mode, stale, drift):
        cleanup = _step_payload(report, "camera_fault_cleanup")
        assert cleanup["close_succeeded"] is True


def test_arm_faults_distinguish_identity_buffer_wire_parse_and_retry_guards() -> None:
    wrong = run_physical_connection_rehearsal(
        fault=RehearsalFault.WRONG_ARM_IDENTITY
    )
    dirty = run_physical_connection_rehearsal(
        fault=RehearsalFault.DIRTY_ARM_BUFFER
    )
    malformed = run_physical_connection_rehearsal(
        fault=RehearsalFault.MALFORMED_T1051_RESPONSE
    )
    retry = run_physical_connection_rehearsal(
        fault=RehearsalFault.RETRY_PROHIBITION
    )

    assert "exactly match" in _step_payload(wrong, "arm_unpowered_identity")[
        "message"
    ]
    assert "buffered bytes" in _step_payload(dirty, "arm_single_t105")[
        "message"
    ]
    assert "response is invalid" in _step_payload(
        malformed, "arm_single_t105"
    )["message"]
    assert "retry prohibited" in _step_payload(
        retry, "arm_retry_prohibition"
    )["message"]
    assert retry.simulated_effects.t105_provider_calls == 2
    assert retry.simulated_effects.t105_wire_attempts == 1
    assert retry.simulated_effects.retry_writes == 0
    feedback = _step_payload(retry, "arm_single_t105")
    assert feedback["write_attempts"] == 1
    assert feedback["retry_count"] == 0


def test_step_evidence_tampering_is_rejected() -> None:
    report = run_physical_connection_rehearsal()
    first = report.steps[0]

    with pytest.raises(PhysicalConnectionRehearsalError, match="does not bind"):
        replace(
            first,
            evidence_canonical_json=first.evidence_canonical_json.replace(
                "host_dependency_receipt", "other_dependency_receipt"
            ),
        )
    with pytest.raises(PhysicalConnectionRehearsalError, match="does not bind"):
        replace(first, evidence_sha256="0" * 64)


def test_public_runner_cannot_accept_a_live_provider_or_device_selector() -> None:
    parameters = inspect.signature(run_physical_connection_rehearsal).parameters

    assert tuple(parameters) == ("run_id", "fault")
    assert all(parameter.kind is inspect.Parameter.KEYWORD_ONLY for parameter in parameters.values())
    with pytest.raises(PhysicalConnectionRehearsalError, match="fault must"):
        run_physical_connection_rehearsal(fault="NONE")  # type: ignore[arg-type]
