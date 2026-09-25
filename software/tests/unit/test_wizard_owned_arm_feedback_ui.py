"""Pure cached display fixtures, not evidence of process/device execution."""

from copy import deepcopy

import pytest

from test_arrival_wizard_arm_power_ui import terminal
from test_arrival_wizard_reopen_ui import browser, commissioning
from test_owned_arm_feedback_runner import runtime


def summary():
    return {
        "schema": "rocell.arm_owned_evidence_summary.v1",
        "status": "COMPLETE_INCAPABLE_EVIDENCE",
        "provenance": "INCAPABLE_NONPURGING_ARM_WORKER",
        "session_id": "session-display-fixture",
        "attempt_id": "attempt-display-fixture",
        **{
            key: "a" * 64
            for key in (
                "source_sha256",
                "permit_sha256",
                "operation_sha256",
                "selected_identity_sha256",
                "worker_registration_sha256",
                "request_sha256",
                "inner_request_sha256",
                "evidence_sha256",
            )
        },
        "process": {
            "status": "SUCCEEDED",
            "process_created": True,
            "initial_thread_resumed": True,
            "tree_exit_confirmed": True,
            "returncode": 0,
            "primary_error": None,
            "cleanup_errors": [],
            "cleanup_error_count": 0,
            "cleanup_errors_omitted": 0,
            "stdin_bytes_written": 1200,
            "stdout_bytes": 800,
            "stdout_sha256": "b" * 64,
            "stderr_bytes": 0,
            "stderr_sha256": "c" * 64,
        },
        "handshake": {
            "ready_retained": True,
            "release_retained": True,
            "child_pid": 1234,
        },
        "feedback": {
            "status": "SUCCEEDED_DIAGNOSTIC",
            "technical_response_valid": True,
            "connection_closed": True,
            "response_bytes": 150,
            "response_sha256": "d" * 64,
            "unexpected_bytes": 0,
            "unexpected_sha256": "e" * 64,
            "unexpected_bytes_unretained": 0,
        },
        "native": {
            "schema": "rocell.arm_native_lifecycle_summary.v1",
            **{
                key: "f" * 64
                for key in (
                    "evidence_sha256",
                    "request_sha256",
                    "controller_binding_sha256",
                    "worker_result_sha256",
                    "late_read_sha256",
                )
            },
            "worker_status": "SUCCEEDED_DIAGNOSTIC",
            "native_cleanup_confirmed": True,
            "resource_counts": {
                "acquired": 3,
                "close_attempted": 3,
                "close_confirmed": 3,
                "unresolved": 0,
            },
            "pending_io_unresolved": False,
            "startup_input_observed": False,
            "native_primary_error": None,
            "native_cleanup_errors": [],
            "late_read_bytes": 0,
            "physical_authority": False,
            "arm_connected": False,
            "device_cleanup_proven": False,
            "final_power_state": "UNKNOWN_REQUIRES_SEPARATE_OBSERVATION",
            "physical_hold": "NONPURGING_SERIAL_INDEPENDENT_PHYSICAL_QUALIFICATION_REQUIRED",
            "meaning": "Modeled owner cleanup, not physical cleanup.",
        },
        "blockers": [],
        "physical_authority": False,
        "arm_connected": False,
        "device_cleanup_proven": False,
        "final_power_state": "UNKNOWN_REQUIRES_SEPARATE_OBSERVATION",
        "meaning": "Display fixture only; no execution or physical observation is asserted.",
    }


def render(value):
    projection = commissioning()
    projection["arm_feedback_process"] = value
    result = browser(projection)
    assert result["status"] == "Local service connected"
    assert result["requests"] == [{"path": "/api/view", "method": "GET", "body": None}]
    assert result["controls"] == browser(commissioning())["controls"]
    return result["text"], terminal(projection)


def contains(output, text):
    """The browser humanizes codes; the terminal preserves their underscores."""
    return text.replace("_", " ") in output.replace("_", " ")


def test_complete_retention_is_separate_from_process_serial_and_power():
    for output in render(summary()):
        for expected in (
            "Contained arm-feedback rehearsal",
            "NOT_CONNECTED / NOT_QUALIFIED",
            "Actual child-process containment and cleanup",
            "Retained admission records",
            "not proof RELEASE was sent",
            "Release retained means planned/retained bytes.",
            "Modeled serial feedback validity",
            "Modeled non-purging native-owner cleanup",
            "Complete evidence means records were retained",
            "None proves physical de-energization",
            "UNKNOWN_REQUIRES_SEPARATE_OBSERVATION",
            "No automatic restart, replay, fallback, discovery or command",
            "attempt-display-fixture",
            "d" * 64,
        ):
            assert expected in output
        assert "ARM_PROCESS_NOT_VERIFIED" not in output


@pytest.mark.parametrize("status", ["FAILED", "CANCELLED", "TIMED_OUT"])
def test_held_process_cannot_be_hidden_by_a_valid_feedback_packet(status):
    value = summary()
    value["status"] = "INCOMPLETE"
    value["process"].update(status=status, primary_error="PROCESS_HELD", returncode=1)
    value["blockers"] = ["OWNED_PROCESS_NOT_COMPLETE"]
    for output in render(value):
        assert contains(output, status) and contains(output, "PROCESS_HELD")
        assert "NOT_CONNECTED / NOT_QUALIFIED" in output
        assert "ARM_PROCESS_NOT_VERIFIED" not in output


def test_complete_evidence_may_retain_a_failed_serial_and_native_cleanup():
    value = summary()
    value["feedback"].update(status="FAILED_UNCERTAIN", connection_closed=False)
    value["native"].update(
        worker_status="FAILED_UNCERTAIN",
        native_cleanup_confirmed=False,
        resource_counts={
            "acquired": 3,
            "close_attempted": 3,
            "close_confirmed": 2,
            "unresolved": 1,
        },
        native_cleanup_errors=[
            {"code": "CLOSE_FAILED", "operation": "close_handle", "winerror": 5}
        ],
    )
    for output in render(value):
        assert contains(output, "FAILED_UNCERTAIN") and contains(output, "CLOSE_FAILED")
        assert "Complete evidence means records were retained" in output
        assert "ARM_PROCESS_NOT_VERIFIED" not in output


@pytest.mark.parametrize(
    "path,bad",
    [
        (("physical_authority",), True),
        (("arm_connected",), True),
        (("device_cleanup_proven",), True),
        (("final_power_state",), "DEENERGIZED"),
        (("status",), "PASS"),
        (("status",), {}),
        (("provenance",), "RECEIVED_HARDWARE"),
        (("raw_serial",), "SENTINEL_DO_NOT_DISPLAY"),
        (("source_sha256",), "not-a-hash"),
        (("process", "status"), []),
        (("process", "tree_exit_confirmed"), 1),
        (("process", "cleanup_error_count"), 1),
        (("process", "returncode"), -1),
        (("process", "stdout_bytes"), 2**53),
        (("process", "raw_stdout"), "SENTINEL_DO_NOT_DISPLAY"),
        (("handshake", "ready_retained"), False),
        (("handshake", "child_pid"), True),
        (("feedback", "technical_response_valid"), "true"),
        (("feedback", "response_bytes"), -1),
        (("native", "physical_authority"), True),
        (("native", "resource_counts", "acquired"), 2),
        (("native", "native_primary_error"), "CLOSE_FAILED"),
        (("native", "late_read_bytes"), 1025),
        (("meaning",), "SENTINEL_DO_NOT_DISPLAY\x1b[1m"),
    ],
)
def test_malformed_summary_is_withheld_without_generic_json_fallback(path, bad):
    value = summary()
    target = value
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = bad
    for output in render(value):
        assert contains(output, "ARM_PROCESS_NOT_VERIFIED")
        assert "SENTINEL_DO_NOT_DISPLAY" not in output
        assert "attempt-display-fixture" not in output


def test_missing_feedback_and_native_remain_explicit_incomplete():
    value = summary()
    value.update(status="INCOMPLETE", feedback=None, native=None)
    for output in render(value):
        assert contains(output, "EVIDENCE_MISSING")
        assert "ARM_PROCESS_NOT_VERIFIED" not in output


def test_display_escapes_text_and_does_not_mutate_caller_summary():
    value = summary()
    value["meaning"] = "<script>do-not-run()</script>"
    before = deepcopy(value)
    for output in render(value):
        assert "<script>do-not-run()</script>" in output
    assert value == before


def test_actual_owned_child_evidence_renders_without_raw_streams(runtime, tmp_path):
    """Actual incapable child/IPC, not a received-arm or physical-port test."""
    from test_owned_arm_feedback_runner import preparation, execute

    prepared = preparation(runtime, tmp_path)
    worker, evidence, calls = execute(prepared)
    value = evidence.safe_summary()
    assert worker.owned_result is not None and worker.owned_result.status == "SUCCEEDED"
    assert value["status"] == "COMPLETE_INCAPABLE_EVIDENCE"
    assert value["feedback"]["technical_response_valid"] is True
    assert value["native"]["native_cleanup_confirmed"] is True
    assert len(calls) == 2
    for output in render(value):
        assert not contains(output, "ARM_PROCESS_NOT_VERIFIED")
        assert value["evidence_sha256"] in output
        assert value["feedback"]["response_sha256"] in output
        assert "NOT_CONNECTED / NOT_QUALIFIED" in output
        assert worker.owned_result.stdout.decode("utf-8") not in output


@pytest.mark.parametrize("inferred", [False, True])
def test_owned_observer_keeps_owned_and_inner_hashes_separate_and_hides_host_time(
    inferred,
):
    from test_arrival_wizard_feedback_ui import projection, observation

    displayed = projection()
    observer = observation()
    observer.update(
        schema="rocell.owned_arm_synthetic_final_power_observation.v1",
        owned_evidence_sha256="a" * 64,
        process_cleanup_used_to_infer_power=inferred,
        observed_monotonic_ns=9223372036854000500,
        worker_finished_monotonic_ns=9223372036854000000,
    )
    displayed["arm_feedback_evaluation"]["final_power_observation"] = observer
    for output in (browser(displayed)["text"], terminal(displayed)):
        assert (
            "9223372036854000500" not in output and "9223372036854000000" not in output
        )
        if inferred:
            assert contains(output, "FINAL_POWER_OBSERVATION_NOT_VERIFIED")
        else:
            assert observer["owned_evidence_sha256"] in output
            assert observer["feedback_evidence_sha256"] in output
            assert "actual inner feedback hash are distinct" in output
        assert (
            "UNKNOWN_REQUIRES_SEPARATE_OBSERVATION" in output
            or "UNKNOWN REQUIRES SEPARATE OBSERVATION" in output
        )
