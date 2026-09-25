"""Restart recovery is a file-only operation, not a renewed hardware session."""

import base64
import json
from pathlib import Path

import pytest

from rocell.application.arrival_wizard_service import ArrivalWizardService
from rocell.application.wizard_actions import WizardError
from test_wizard_native_arm_integration import (
    setup,
    action,
    ticket,
    WORKSPACE,
    FixtureRunner,
)
from test_passive_arm_attempt_store import journal, ATTEMPT

ACTION = "inspect_physical_passive_history"


def test_restart_inspection_exports_originals_without_current_setup(setup):
    old, _, _, directory = setup("physical")
    old._log.root.mkdir()
    attempt = journal(old._log.root)
    attempt.consume(now_monotonic_ns=3_000_000_000)
    # Model a partially published claim without modifying production/user files.
    claim = old._log.root / (ATTEMPT + "-physical-passive-claimed.json")
    claim.write_bytes(b"partial\xff")
    old.shutdown()
    runner = FixtureRunner("physical")
    new = ArrivalWizardService(
        WORKSPACE,
        mode="physical",
        runner=runner,
        log_directory=directory / "logs",
        export_directory=directory / "restarted-exports",
    )
    try:
        result = action(new, ACTION, attempt_id=ATTEMPT)
        assert result["status"] == "SUCCEEDED", result
        report = result["result"]["steps"][0]["report"]
        assert report["stages"]["claimed"]["status"] == "BYTES_COLLECTED_NOT_VALIDATED"
        assert report["historical_only"] is True
        assert new._passive_arm_setup is None
        with pytest.raises(WizardError):
            ticket(new, "run_passive_arm_connection")
        exported = action(new, "export_logs")
        assert exported["status"] == "SUCCEEDED", exported
        folder = Path(exported["result"]["receipt"]["path"])
        saved = json.loads(
            (folder / "attachment-physical-passive-history.json").read_bytes()
        )
        raw = b"".join(
            base64.b64decode(part, validate=True)
            for part in saved["stages"]["claimed"]["base64_chunks"]
        )
        assert raw == b"partial\xff"
        assert runner.calls == []
    finally:
        new.shutdown()


def test_no_saved_files_is_not_success(setup):
    service, runner, _, _ = setup("physical")
    result = action(service, ACTION, attempt_id=ATTEMPT)
    assert result["status"] == "FAILED"
    assert runner.calls == []


@pytest.mark.parametrize("value", ["../escape", "COM6", "operation-wrong"])
def test_path_input_rejected_before_queue(setup, value):
    service, runner, _, _ = setup("physical")
    with pytest.raises(WizardError):
        ticket(service, ACTION, attempt_id=value)
    assert runner.calls == []
