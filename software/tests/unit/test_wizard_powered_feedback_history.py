"""Public recovery of exact historical bytes with device providers forbidden."""

import base64
import hashlib
import json
from pathlib import Path

import pytest

from rocell.application.powered_feedback_attempt_store import attempt_path
from rocell.application.wizard_diagnostic_export import verify_export
from test_wizard_native_arm_integration import setup, action

ACTION = "inspect_powered_feedback_history"
ATTEMPT = "operation-" + "f" * 32


@pytest.mark.parametrize("mode", ["rehearsal", "physical"])
def test_partial_original_survives_public_history_and_export(setup, mode):
    service, runner, _, _ = setup(mode)
    service._log.root.mkdir()
    raw = b'{"partial-consumption":\xff'
    path = attempt_path(service._log.root, ATTEMPT, "consumed")
    path.write_bytes(raw)
    completed = action(service, ACTION, attempt_id=ATTEMPT)
    assert completed["status"] == "SUCCEEDED", completed
    report = completed["result"]["steps"][0]["report"]
    assert report["status"] == "HISTORICAL_BYTES_ONLY"
    assert (
        report["chain_verified"]
        is report["replay_allowed"]
        is report["connected"]
        is False
    )
    assert report["records"][1]["sha256"] == hashlib.sha256(raw).hexdigest()
    for index in range(10):
        action(service, "record_note", note=f"History retention {index}")
    exported = action(service, "export_logs")
    assert exported["status"] == "SUCCEEDED", exported
    folder = Path(exported["result"]["receipt"]["path"])
    assert verify_export(folder)["valid"] is True
    data = json.loads(
        (folder / "attachment-powered-feedback-history.json").read_bytes()
    )
    recovered = b"".join(
        base64.b64decode(chunk, validate=True)
        for chunk in data["records"][1]["base64_chunks"]
    )
    assert recovered == path.read_bytes() == raw
    assert runner.calls == []


def test_missing_attempt_is_not_success(setup):
    service, runner, _, _ = setup("physical")
    completed = action(service, ACTION, attempt_id=ATTEMPT)
    assert completed["status"] == "FAILED", completed
    report = completed["result"]["steps"][0]["report"]
    assert report["status"] == "NO_READABLE_HISTORY"
    assert all(record["status"] == "MISSING" for record in report["records"])
    assert runner.calls == []


def test_traversal_attempt_cannot_read_foreign_file(setup):
    service, runner, _, _ = setup("physical")
    result = action(service, ACTION, attempt_id="../foreign")
    assert result["status"] == "FAILED"
    assert service._powered_feedback_history_files is None
    assert runner.calls == []


def test_unreadable_stage_is_reported_and_does_not_claim_success(setup):
    service, runner, _, _ = setup("physical")
    service._log.root.mkdir()
    attempt_path(service._log.root, ATTEMPT, "prepared").write_bytes(b"readable partial")
    attempt_path(service._log.root, ATTEMPT, "consumed").mkdir()
    result = action(service, ACTION, attempt_id=ATTEMPT)
    assert result["status"] == "FAILED"
    report = result["result"]["steps"][0]["report"]
    assert report["records"][0]["status"] == "BYTES_RETAINED"
    assert report["records"][1]["status"] == "UNREADABLE"
    assert report["chain_verified"] is False
    assert action(service, "export_logs")["status"] == "SUCCEEDED"
    assert runner.calls == []
