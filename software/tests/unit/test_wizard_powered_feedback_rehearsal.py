"""Public wizard rehearsal and exported originals, with host I/O forbidden."""

import base64
import hashlib
import json
from pathlib import Path

import pytest

from rocell.application.wizard_actions import WizardError
from rocell.application.wizard_diagnostic_export import verify_export
from test_wizard_native_arm_integration import setup, action, ticket

ACTION = "rehearse_powered_arm_feedback"


@pytest.mark.parametrize(
    "scenario,expected",
    [
        ("nominal", "SUCCEEDED"),
        ("stale-input", "FAILED"),
        ("incomplete-reply", "FAILED"),
        ("short-write", "FAILED"),
        ("cleanup-unknown", "FAILED"),
    ],
)
def test_public_action_and_export(setup, scenario, expected):
    service, runner, _, _ = setup("rehearsal")
    completed = action(service, ACTION, scenario=scenario)
    assert completed["status"] == expected, completed
    report = completed["result"]["steps"][0]["report"]
    assert report["origin"] == "SYNTHETIC_REHEARSAL"
    assert report["connected"] is False
    assert report["process_created"] is True
    assert report["process_tree_exit_confirmed"] is True
    assert report["process_status"] == "SUCCEEDED"
    assert report["process_outcome_saved"] is True
    if scenario == "nominal":
        for index in range(10):
            assert (
                action(service, "record_note", note=f"Retention {index}")["status"]
                == "SUCCEEDED"
            )
    exported = action(service, "export_logs")
    assert exported["status"] == "SUCCEEDED", exported
    folder = Path(exported["result"]["receipt"]["path"])
    assert verify_export(folder)["valid"] is True
    wrapper = json.loads(
        (folder / "attachment-powered-feedback-rehearsal.json").read_bytes()
    )
    raw = base64.b64decode(wrapper["original_base64"], validate=True)
    assert hashlib.sha256(raw).hexdigest() == report["original_sha256"]
    original = json.loads(raw)
    assert original["scenario"] == scenario
    assert original["observation"]["physical_authority"] is False
    assert original["operation_id"] == completed["operation_id"]
    process_wrapper = json.loads(
        (folder / "attachment-powered-feedback-process.json").read_bytes()
    )
    process_raw = base64.b64decode(process_wrapper["original_base64"], validate=True)
    assert (
        hashlib.sha256(process_raw).hexdigest() == report["process_diagnostic_sha256"]
    )
    process = json.loads(process_raw)
    saved_path = (
        service._log.root
        / (completed["operation_id"] + "-powered-feedback-child")
        / "process-outcome.json"
    )
    assert saved_path.read_bytes() == process_raw
    child_wire = json.loads(base64.b64decode(process["stdout_base64"], validate=True))
    assert base64.b64decode(child_wire["original_base64"], validate=True) == raw
    if scenario == "nominal":
        from copy import deepcopy
        from rocell.providers.windows.powered_feedback_process_codec import validate_result
        for field, value in (("connected", True), ("attempt_id", "operation-" + "f" * 32)):
            changed = deepcopy(child_wire)
            changed[field] = value
            with pytest.raises(ValueError):
                validate_result(changed, payload=process["payload"],
                    request_sha256=process["process"]["request_sha256"], attempt_id=completed["operation_id"])
    assert runner.calls == []


def test_pre_cancelled_supervised_operation_never_starts_child(setup):
    from threading import Event
    import time
    from rocell.application.wizard_powered_feedback_coordinator import (
        run_supervised_rehearsal,
    )

    service, runner, _, _ = setup("rehearsal")
    cancel = Event()
    service._log.root.mkdir()
    cancel.set()
    result, original, diagnostic = run_supervised_rehearsal(
        root=service._log.root,
        session_id=service.session_id,
        operation_id="operation-" + "d" * 32,
        source_sha256=service.source_sha256,
        scenario="nominal",
        cancellation=cancel,
        deadline_ns=time.monotonic_ns() + 20_000_000_000,
        recheck_source=lambda: None,
    )
    assert result["status"] == "CANCELLED"
    assert json.loads(diagnostic)["process"]["process_created"] is False
    assert original == diagnostic
    assert runner.calls == []


def test_physical_mode_cannot_run_rehearsal_as_live_feedback(setup):
    service, runner, _, _ = setup("physical")
    with pytest.raises(WizardError):
        ticket(service, ACTION, scenario="nominal")
    assert runner.calls == []
