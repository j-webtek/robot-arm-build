"""Classify a sealed worker outcome without starting any process or device."""

from copy import deepcopy
from dataclasses import replace

import pytest

from rocell.application.wizard_powered_feedback_native_coordinator import PoweredFeedbackOutcome
from rocell.providers.windows.owned_worker_process import OwnedWorkerResult


def outcome():
    observation = {
        "status": "FAILED", "errors": ["FEEDBACK_DEADLINE_EXCEEDED"],
        "feedback": None,
        "lifecycle": {"cleanup_confirmed": True, "confirmed_write_bytes": 10},
        **{name: {"bytes": 0} for name in ("startup", "response", "late_cleanup_input")},
    }
    process = OwnedWorkerResult(
        status="SUCCEEDED", primary_error=None, cleanup_errors=(),
        request_sha256="a" * 64, attempt_id="operation-" + "b" * 32,
        process_created=True, initial_thread_resumed=True, tree_exit_confirmed=True,
        returncode=0, elapsed_ns=1, stdin_bytes_written=1,
        peak_observed_handles=0, peak_active_processes=1,
        stdout=b"", stderr=b"", parsed_result={"child_result": {"observation": observation}},
    )
    return PoweredFeedbackOutcome(process, "c" * 64, None)


def test_clean_silent_timeout_is_failed_not_connected():
    result = outcome().publication()
    assert result["status"] == "FAILED"
    assert result["code"] == "POWERED_QUERY_WRITTEN_NO_REPLY"
    report = result["steps"][0]["report"]
    assert report["response_bytes"] == 0
    assert report["connected"] is report["motion_authorized"] is False
    assert "LiDAR" in report["next_step"]


@pytest.mark.parametrize("case", ["partial", "missing", "cleanup", "short", "process", "persistence"])
def test_other_failures_are_not_reported_as_clean_silent_timeout(case):
    value = outcome()
    parsed = deepcopy(value.process.parsed_result)
    observation = parsed["child_result"]["observation"]
    if case == "partial":
        observation["response"]["bytes"] = 4
    elif case == "missing":
        del observation["response"]
    elif case == "cleanup":
        observation["lifecycle"]["cleanup_confirmed"] = False
    elif case == "short":
        observation["lifecycle"]["confirmed_write_bytes"] = 2
    value = replace(value, process=replace(value.process, parsed_result=parsed))
    if case == "process":
        value = replace(value, process=replace(value.process, tree_exit_confirmed=False))
    if case == "persistence":
        value = replace(value, persistence_error="fixture disk failure")
    assert value.publication()["code"] != "POWERED_QUERY_WRITTEN_NO_REPLY"
    assert value.publication()["status"] == "FAILED"
