"""Public wizard queue/export with a real incapable owned child; no serial I/O."""

import base64
import hashlib
import json
from pathlib import Path

import pytest

from rocell.application.wizard_actions import WizardError
from rocell.application.wizard_diagnostic_export import verify_export
from rocell.application.passive_arm_diagnostic_checkpoint import (
    recover,
    recover_attempt,
)
from rocell.application.wizard_diagnostic_log import WizardDiagnosticLog
from test_arrival_wizard_service import make_service, _ticket, _complete
from test_wizard_native_arm_ui import render


ACTION = "rehearse_passive_arm_connection"


def perform(service, name, values):
    receipt = service.execute_action(_ticket(service, name, values)["ticket_id"])
    return _complete(service, receipt["operation_id"])


def test_preview_is_inert_and_physical_mode_is_unavailable(make_service):
    service, runner, _ = make_service()
    ticket = _ticket(service, ACTION, {"scenario": "nominal"})
    assert ticket["physical_authority"] is False and not runner.calls
    assert service.view()["operations"] == []
    physical, _, _ = make_service(mode="physical")
    with pytest.raises(WizardError):
        _ticket(physical, ACTION, {"scenario": "nominal"})


def test_intent_publication_failure_prevents_dispatch(make_service, monkeypatch):
    from rocell.application import passive_arm_diagnostic_checkpoint as checkpoint
    from rocell.application import passive_arm_rehearsal as rehearsal

    calls = []

    def fail(*args, **kwargs):
        raise OSError("Injected intent storage failure")

    def forbidden(*args, **kwargs):
        calls.append("dispatch")
        raise AssertionError("Cannot dispatch without persisted intent")

    monkeypatch.setattr(checkpoint, "publish_intent", fail)
    monkeypatch.setattr(rehearsal.OwnedWindowsWorker, "run", forbidden)
    service, _, _ = make_service()
    operation = perform(service, ACTION, {"scenario": "nominal"})
    assert operation["status"] == "FAILED"
    assert calls == []


def test_dispatch_observes_prior_intent_and_failure_does_not_enable_replay(
    make_service, monkeypatch
):
    from rocell.application import passive_arm_rehearsal as rehearsal
    from rocell.application.passive_arm_diagnostic_checkpoint import read_intent

    service, _, _ = make_service()
    observed = []

    def fail_after_intent(*args, **kwargs):
        path = service._log.root / (service.session_id + "-passive-intent.json")
        observed.append(read_intent(path))
        raise RuntimeError("Injected dispatch interruption; no real child launched")

    monkeypatch.setattr(rehearsal.OwnedWindowsWorker, "run", fail_after_intent)
    operation = perform(service, ACTION, {"scenario": "nominal"})
    assert operation["status"] == "FAILED" and len(observed) == 1
    recovery = recover_attempt(service._log.root, service.session_id)
    assert recovery["status"] == "OUTCOME_UNBOUND_NO_REPLAY"
    assert recovery["replay_allowed"] is False
    with pytest.raises(WizardError, match="One passive rehearsal"):
        _ticket(service, ACTION, {"scenario": "nominal"})


@pytest.mark.parametrize(
    "scenario",
    [
        "nominal",
        "open-failed",
        "cleanup-unknown",
        "malformed",
        "wrong-binding",
        "stall",
        "lifecycle-nominal",
        "lifecycle-open-failed",
        "lifecycle-cleanup-unknown",
    ],
)
def test_public_attempt_preserves_original_raw_process_output(make_service, scenario):
    service, runner, _ = make_service()
    operation = perform(service, ACTION, {"scenario": scenario})
    assert operation["status"] == (
        "SUCCEEDED" if scenario in {"nominal", "lifecycle-nominal"} else "FAILED"
    ), operation
    assert operation["completion_log_persisted"] is True
    report = operation["result"]["steps"][0]["report"]
    if scenario.startswith("lifecycle-"):
        lifecycle = report["process"]["parsed_result"]["lifecycle"]
        assert lifecycle["confirmed_write_bytes"] == 0
        assert lifecycle["api_calls"]["create_file"] == 1
        if scenario == "lifecycle-nominal":
            assert lifecycle["settings_readback_verified"] is True
            assert lifecycle["cleanup_confirmed"] is True
    assert report["process"]["process_created"] is True
    assert report["references_are_commissioning_evidence"] is False
    raw = base64.b64decode(report["raw_stdout_base64"])
    assert hashlib.sha256(raw).hexdigest() == report["process"]["stdout_sha256"]
    assert (
        report["connected"]
        is report["qualified"]
        is report["physical_authority"]
        is False
    )
    assert not runner.calls  # Not delegated to an unowned diagnostic subprocess.
    checkpoint = service.view()["passive_arm_rehearsal"]["durable_checkpoint"]
    assert checkpoint["status"] == "VERIFIED_DIAGNOSTIC_ONLY"
    historical = recover(Path(checkpoint["path"]))
    assert historical["retained"]["result"] == operation["result"]
    assert historical["connected"] is historical["replay_allowed"] is False
    paired = recover_attempt(service._log.root, service.session_id)
    assert paired["status"] == "HISTORICAL_PAIR_VERIFIED"
    assert paired["replay_allowed"] is paired["authenticated"] is False
    assert WizardDiagnosticLog.verify(service._log.directory)["replay_allowed"] is False
    if scenario == "nominal":
        for text in render(service.view()):
            assert "Retained passive USB rehearsal" in text
            assert "OBSERVED_CLOSED" in text or "OBSERVED CLOSED" in text
        assert not runner.calls
    with pytest.raises(WizardError, match="One passive rehearsal"):
        _ticket(service, ACTION, {"scenario": "nominal"})
    exported = perform(service, "export_logs", {})
    assert exported["status"] == "SUCCEEDED", exported
    directory = Path(exported["result"]["receipt"]["path"])
    assert verify_export(directory)["valid"] is True
    retained = json.loads(
        (directory / "attachment-passive-arm-rehearsal.json").read_bytes()
    )
    assert retained["result"] == operation["result"]


def test_checkpoint_survives_shutdown_without_restoring_authority(make_service):
    service, _, _ = make_service()
    original = perform(service, ACTION, {"scenario": "nominal"})
    path = Path(service.view()["passive_arm_rehearsal"]["durable_checkpoint"]["path"])
    service.shutdown()
    recovered = recover(path)
    assert recovered["retained"]["result"] == original["result"]
    assert recovered["status"] == "HISTORICAL_DIAGNOSTIC_ONLY"
    fresh, runner, _ = make_service()
    assert fresh.view()["passive_arm_rehearsal"] is None
    assert not runner.calls


def test_checkpoint_failure_keeps_raw_result_and_fails_operation(
    make_service, monkeypatch
):
    from rocell.application import passive_arm_diagnostic_checkpoint as checkpoint

    def fail(*args, **kwargs):
        raise OSError("Injected full disk")

    monkeypatch.setattr(checkpoint, "publish", fail)
    service, _, _ = make_service()
    operation = perform(service, ACTION, {"scenario": "nominal"})
    assert operation["status"] == "FAILED"
    assert operation["error"]["code"] == "PASSIVE_CHECKPOINT_UNCONFIRMED"
    assert operation["result"]["steps"][0]["report"]["raw_stdout_base64"]
    assert (
        service.view()["passive_arm_rehearsal"]["durable_checkpoint"]["status"]
        == "PERSISTENCE_UNCONFIRMED"
    )
    exported = perform(service, "export_logs", {})
    assert exported["status"] == "SUCCEEDED"


def test_notes_cannot_evict_passive_attempt_from_export(make_service):
    service, _, _ = make_service()
    operation = perform(service, ACTION, {"scenario": "nominal"})
    for index in range(9):
        assert (
            perform(service, "record_note", {"note": f"Retention test {index}"})[
                "status"
            ]
            == "SUCCEEDED"
        )
    assert service.operation(operation["operation_id"])["result"] is None
    exported = perform(service, "export_logs", {})
    assert exported["status"] == "SUCCEEDED", exported
    directory = Path(exported["result"]["receipt"]["path"])
    retained = json.loads(
        (directory / "attachment-passive-arm-rehearsal.json").read_bytes()
    )
    assert retained["operation_id"] == operation["operation_id"]
    assert retained["result"] == operation["result"]
