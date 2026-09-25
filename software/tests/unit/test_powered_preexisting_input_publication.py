"""Stream/query guidance classifies retained outcomes, never opens hardware."""

from copy import deepcopy
from dataclasses import replace

import pytest

from test_powered_no_reply_publication import outcome


def preexisting_outcome():
    value = outcome()
    parsed = deepcopy(value.process.parsed_result)
    observation = parsed["child_result"]["observation"]
    observation["errors"] = ["PREEXISTING_INPUT"]
    observation["startup"]["bytes"] = 128
    observation["lifecycle"]["confirmed_write_bytes"] = 0
    return replace(value, process=replace(value.process, parsed_result=parsed))


def test_preexisting_input_guidance_preserves_failed_closed_zero_authority():
    result = preexisting_outcome().publication()
    assert result["code"] == "POWERED_INPUT_BEFORE_QUERY"
    assert result["status"] == "FAILED"
    report = result["steps"][0]["report"]
    assert report["confirmed_write_bytes"] == 0
    assert report["serial_cleanup_confirmed"] is True
    assert report["process_tree_exit_confirmed"] is True
    assert report["feedback"] is None
    assert report["connected"] is report["motion_authorized"] is False
    assert report["physical_authority"] is result["physical_authority"] is False
    assert "new reviewed launch" in report["next_step"]
    assert "Capture arm telemetry (no commands)" in report["next_step"]
    assert "Do not purge input or retry" in report["next_step"]


@pytest.mark.parametrize("case", [
    "empty", "missing_startup", "boolean_count", "missing_write", "boolean_write",
    "partial_write", "cleanup", "extra_error", "wrong_status", "process_failed",
    "not_created", "not_resumed", "tree_unknown", "cancelled", "timed_out",
    "persistence", "missing_digest",
])
def test_ambiguous_or_incomplete_attempt_never_gets_clean_stream_guidance(case):
    value = preexisting_outcome()
    parsed = deepcopy(value.process.parsed_result)
    observation = parsed["child_result"]["observation"]
    if case == "empty":
        observation["startup"]["bytes"] = 0
    elif case == "missing_startup":
        del observation["startup"]
    elif case == "boolean_count":
        observation["startup"]["bytes"] = True
    elif case == "missing_write":
        del observation["lifecycle"]["confirmed_write_bytes"]
    elif case == "boolean_write":
        observation["lifecycle"]["confirmed_write_bytes"] = False
    elif case == "partial_write":
        observation["lifecycle"]["confirmed_write_bytes"] = 1
    elif case == "cleanup":
        observation["lifecycle"]["cleanup_confirmed"] = False
    elif case == "extra_error":
        observation["errors"].append("UNRESOLVED_IO")
    elif case == "wrong_status":
        observation["status"] = "UNKNOWN"
    value = replace(value, process=replace(value.process, parsed_result=parsed))
    process_changes = {
        "process_failed": {"status": "FAILED"},
        "not_created": {"process_created": False},
        "not_resumed": {"initial_thread_resumed": False},
        "tree_unknown": {"tree_exit_confirmed": False},
        "cancelled": {"status": "CANCELLED"},
        "timed_out": {"status": "TIMED_OUT"},
    }
    if case in process_changes:
        value = replace(value, process=replace(value.process, **process_changes[case]))
    elif case == "persistence":
        value = replace(value, persistence_error="injected disk failure")
    elif case == "missing_digest":
        value = replace(value, outcome_sha256=None)
    result = value.publication()
    assert result["code"] != "POWERED_INPUT_BEFORE_QUERY"
    assert result["status"] != "SUCCEEDED"
    assert result["steps"][0]["report"]["next_step"] is None
