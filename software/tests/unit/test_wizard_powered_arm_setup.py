"""Powered operator observations through the real service, without device I/O."""

import base64
import hashlib
import json
from pathlib import Path

import pytest

from rocell.application import wizard_powered_arm_setup as producer
from rocell.application.wizard_actions import WizardError
from test_wizard_native_arm_integration import setup, action, ticket
from test_wizard_passive_arm_setup import (
    ready,
    ACTION as USB_SETUP,
    VALUES as USB_VALUES,
)

ACTION = "record_powered_arm_startup"
VALUES = dict(
    operator_id="fixture-operator",
    adapter_on=True,
    usb_connected=True,
    secured_and_clear=True,
    stationary=True,
    startup_motion="observed",
)


def test_powered_report_invalidates_usb_setup_and_exports_original(setup):
    service, runner, _, _ = ready(setup)
    assert action(service, USB_SETUP, **USB_VALUES)["status"] == "SUCCEEDED"
    assert service._passive_arm_setup is not None
    calls = list(runner.calls)
    result = action(service, ACTION, **VALUES)
    assert result["status"] == "SUCCEEDED", result
    assert service._passive_arm_setup is None
    receipt = result["result"]["steps"][0]["report"]
    raw = Path(receipt["path"]).read_bytes()
    original = json.loads(raw)
    assert original["reported"]["external_adapter_on"] is True
    assert original["installed_firmware_identity"] == "UNKNOWN"
    assert original["supply_voltage_measurement"] is None
    assert original["feedback_authorized"] is original["motion_authorized"] is False
    assert hashlib.sha256(raw).hexdigest() == receipt["sha256"]
    with pytest.raises(WizardError):
        ticket(service, "run_passive_arm_connection")
    exported = action(service, "export_logs")
    assert exported["status"] == "SUCCEEDED", exported
    directory = Path(exported["result"]["receipt"]["path"])
    saved = json.loads(
        (directory / "attachment-powered-arm-startup-original.json").read_bytes()
    )
    assert base64.b64decode(saved["original_base64"], validate=True) == raw
    assert runner.calls == calls


def test_failed_power_record_still_invalidates_usb_only_approval(setup, monkeypatch):
    service, _, _, _ = ready(setup)
    action(service, USB_SETUP, **USB_VALUES)

    def fail(*args, **kwargs):
        raise OSError("fixture disk failure")

    monkeypatch.setattr(producer, "publish_bytes", fail)
    result = action(service, ACTION, **VALUES)
    assert result["status"] == "FAILED"
    assert service._passive_arm_setup is None


@pytest.mark.parametrize(
    "field", ["adapter_on", "usb_connected", "secured_and_clear", "stationary"]
)
def test_unconfirmed_reports_are_not_defaulted_to_true(setup, field):
    service, runner, _, _ = setup("physical")
    with pytest.raises(WizardError):
        ticket(service, ACTION, **{**VALUES, field: False})
    assert runner.calls == []


def test_rehearsal_cannot_record_a_physical_power_report(setup):
    service, _, _, _ = setup("rehearsal")
    with pytest.raises(WizardError):
        ticket(service, ACTION, **VALUES)
