"""Public action wiring using cancellation before child/native access."""

import pytest
import json
import base64
from pathlib import Path
from dataclasses import replace

from rocell.application import wizard_passive_arm_coordinator as coordinator
from rocell.application.wizard_actions import WizardError
from test_wizard_native_arm_integration import setup, action, ticket, inspect
from test_wizard_passive_arm_setup import ready, VALUES, ACTION as SETUP

ACTION = "run_passive_arm_connection"


def test_preparation_failure_still_exports_named_attempt(setup, monkeypatch):
    service, runner, _, _ = ready(setup)
    action(service, SETUP, **VALUES)

    def fail(**kwargs):
        raise OSError("fixture journal storage failure")

    monkeypatch.setattr(coordinator, "prepare_attempt", fail)
    result = action(service, ACTION)
    assert result["status"] == "FAILED"
    assert service._passive_arm_outcome is None
    exported = action(service, "export_logs")
    assert exported["status"] == "SUCCEEDED", exported
    directory = Path(exported["result"]["receipt"]["path"])
    history = json.loads(
        (directory / "attachment-passive-arm-attempt-files.json").read_bytes()
    )
    assert history["attempt_id"] == result["operation_id"]
    assert all(stage["status"] == "MISSING" for stage in history["stages"].values())
    assert history["authenticated"] is False


def test_missing_setup_blocks_preview(setup):
    service, _, _, _ = ready(setup)
    with pytest.raises(WizardError):
        ticket(service, ACTION)


def test_changed_metadata_blocks_prepared_attempt(setup):
    service, _, _, _ = ready(setup)
    action(service, SETUP, **VALUES)
    prepared = ticket(service, ACTION)
    inspect(service)
    with pytest.raises(WizardError):
        service.execute_action(prepared["ticket_id"])


def test_public_attempt_retains_cancelled_process_and_blocks_replay(setup, monkeypatch):
    service, runner, _, _ = ready(setup)
    action(service, SETUP, **VALUES)
    calls = list(runner.calls)
    original = coordinator.PassiveArmCoordinator.run

    def cancelled(self, **values):
        values["cancellation"].set()
        return original(self, **values)

    monkeypatch.setattr(coordinator.PassiveArmCoordinator, "run", cancelled)
    result = action(service, ACTION)
    assert result["status"] in {"FAILED", "CANCELLED"}, result
    retained = service._passive_arm_outcome
    assert retained is not None, result
    assert not retained.process.process_created
    assert retained.outcome_sha256
    assert service._passive_arm_publication["physical_authority"] is False
    assert runner.calls == calls
    with pytest.raises(WizardError):
        ticket(service, ACTION)
    # Exercise the exporter's string cap using synthetic maximum-sized logs.
    raw = bytes(range(256)) * 1024
    service._passive_arm_outcome = replace(
        retained, process=replace(retained.process, stdout=raw, stderr=b"\xfffixture")
    )
    exported = action(service, "export_logs")
    assert exported["status"] == "SUCCEEDED", exported
    directory = Path(exported["result"]["receipt"]["path"])
    history = json.loads(
        (directory / "attachment-passive-arm-attempt-files.json").read_bytes()
    )
    assert history["attempt_id"] == result["operation_id"]
    assert history["stages"]["consumed"]["status"] == "BYTES_COLLECTED_NOT_VALIDATED"
    assert history["stages"]["claimed"]["status"] == "MISSING"
    assert history["replay_allowed"] is False
    payload = json.loads(
        (directory / "attachment-passive-arm-process-logs.json").read_bytes()
    )
    assert (
        b"".join(
            base64.b64decode(chunk, validate=True)
            for chunk in payload["streams"]["stdout"]["base64_chunks"]
        )
        == raw
    )
