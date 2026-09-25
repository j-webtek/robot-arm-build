"""Public wizard setup-original flow; arm/camera/process calls forbidden."""

import hashlib
import base64
import json
from pathlib import Path

import pytest

from rocell.application.wizard_actions import WizardError
from rocell.application.wizard_diagnostic_export import verify_export
from test_wizard_native_arm_integration import (
    setup,
    generic_review,
    inspect,
    action,
    ticket,
)

ACTION = "record_passive_arm_setup"
VALUES = dict(
    operator_id="fixture-operator", power_disconnected=True, secured_and_clear=True
)


def ready(setup):
    service, runner, source, directory = setup("physical")
    generic_review(service)
    inspect(service)
    return service, runner, source, directory


def test_public_action_retains_exact_original_and_exports(setup):
    service, runner, _, _ = ready(setup)
    calls = list(runner.calls)
    operation = action(service, ACTION, **VALUES)
    assert operation["status"] == "SUCCEEDED", operation
    receipt = operation["result"]["steps"][0]["report"]
    raw = Path(receipt["path"]).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == receipt["sha256"]
    original = json.loads(raw)
    assert original["operator_report"]["external_adapter_disconnected"] is True
    assert original["measured_isolation"] == "NOT_ESTABLISHED"
    assert original["source_sha256"] == "a" * 64
    assert original["connected"] is original["physical_authority"] is False
    assert runner.calls == calls
    exported = action(service, "export_logs")
    assert exported["status"] == "SUCCEEDED", exported
    path = Path(exported["result"]["receipt"]["path"])
    assert verify_export(path)["valid"] is True
    attachment = json.loads(
        (path / "attachment-passive-arm-setup-original.json").read_bytes()
    )
    assert base64.b64decode(attachment["original_base64"], validate=True) == raw
    assert attachment["original_sha256"] == receipt["sha256"]


def test_missing_metadata_disables_action(setup):
    service, runner, _, _ = setup("physical")
    with pytest.raises(WizardError):
        ticket(service, ACTION, **VALUES)
    assert runner.calls == []


def test_rehearsal_cannot_record_physical_setup(setup):
    service, _, _, _ = setup("rehearsal")
    generic_review(service)
    inspect(service)
    with pytest.raises(WizardError):
        ticket(service, ACTION, **VALUES)


@pytest.mark.parametrize("field", ["power_disconnected", "secured_and_clear"])
def test_unchecked_operator_report_rejected_at_preview(setup, field):
    service, _, _, _ = ready(setup)
    values = {**VALUES, field: False}
    with pytest.raises(WizardError):
        ticket(service, ACTION, **values)


def test_source_change_prevents_setup_publication(setup):
    service, _, source, _ = ready(setup)
    prepared = ticket(service, ACTION, **VALUES)
    source["hash"] = "b" * 64
    with pytest.raises(WizardError):
        service.execute_action(prepared["ticket_id"])


def test_changed_native_report_rejects_prepared_ticket(setup):
    service, _, _, _ = ready(setup)
    prepared = ticket(service, ACTION, **VALUES)
    inspect(service)
    with pytest.raises(WizardError):
        service.execute_action(prepared["ticket_id"])


def test_bad_operator_id_rejected_before_queue(setup):
    service, _, _, _ = ready(setup)
    with pytest.raises(WizardError):
        ticket(service, ACTION, **{**VALUES, "operator_id": "../not-an-operator"})


def test_publication_failure_is_not_success_or_device_access(setup, monkeypatch):
    from rocell.application import wizard_passive_arm_setup as producer

    service, runner, _, _ = ready(setup)
    calls = list(runner.calls)

    def fail(*args, **kwargs):
        raise OSError("modeled failed original write")

    monkeypatch.setattr(producer, "publish_bytes", fail)
    result = action(service, ACTION, **VALUES)
    assert result["status"] == "FAILED"
    assert runner.calls == calls


def test_both_interfaces_show_setup_action_without_dispatch():
    from rocell.application.wizard_actions import ACTION_BY_ID
    from test_wizard_native_arm_ui import produced, render

    view, _ = produced()
    view["mode"] = "physical"
    view["actions"] = [ACTION_BY_ID[ACTION].view(mode="physical", busy=False)]
    for output in render(view):
        assert "Record USB-only arm setup" in output
