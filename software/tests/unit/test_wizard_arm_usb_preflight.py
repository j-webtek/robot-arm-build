"""Preflight harness tests; actual device/process calls are forbidden by setup."""

import importlib.util
from pathlib import Path

import pytest

from test_wizard_native_arm_integration import setup  # noqa: F401


@pytest.fixture
def script():
    path = Path(__file__).resolve().parents[2] / "scripts/wizard_arm_usb_preflight.py"
    spec = importlib.util.spec_from_file_location("usb_preflight_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def inputs():
    return dict(
        vid="fffe",
        pid="0002",
        unit_serial="SYNTHETIC-ARM-A",
        reviewer="test-reviewer",
        power_disconnected=True,
    )


def test_public_workflow_exports_without_device_authority(script, setup):
    service, runner, _, directory = setup("physical")
    result = script.run_preflight(service, **inputs())
    assert result["connected"] is False
    assert result["physical_authority"] is False
    assert Path(result["export_directory"]).parent == directory / "chosen-exports"
    assert [call[0] for call in runner.calls] == [
        "inventory_devices",
        "inspect_native_arm_metadata",
    ]
    assert result["native_arm_metadata"]["report"]["status"] == "METADATA_CORRELATED"


def test_power_acknowledgement_required_before_any_action(script, setup):
    service, runner, _, _ = setup("physical")
    values = inputs()
    values["power_disconnected"] = False
    with pytest.raises(ValueError, match="power"):
        script.run_preflight(service, **values)
    assert runner.calls == []


def test_no_rehearsal_promotion(script, setup):
    service, runner, _, _ = setup("rehearsal")
    with pytest.raises(ValueError, match="Physical"):
        script.run_preflight(service, **inputs())
    assert runner.calls == []


@pytest.mark.parametrize(
    "action", ["arm_connect", "initialize", "physical_camera_probe"]
)
def test_no_connection_or_camera_actions(script, action):
    with pytest.raises(ValueError, match="Only metadata"):
        script.perform(None, action, {})


@pytest.mark.parametrize("rows", [[], [1, 1], [2]])
def test_selection_missing_duplicate_or_blocked(script, rows):
    candidates = [
        dict(
            vid="10c4",
            pid="ea60",
            unit_serial="unit",
            choice_id="choice",
            identity_blockers=[] if row == 1 else ["BLOCKED"],
        )
        for row in rows
    ]
    view = {"device_selection": {"devices": {"SERIAL": {"candidates": candidates}}}}
    with pytest.raises(ValueError):
        script.select_candidate(view, "10c4", "ea60", "unit")


def test_unknown_outcome_starts_no_export_or_retry(script, setup, monkeypatch):
    service, _, _, _ = setup("physical")
    calls = []

    def pending(service, name, values):
        calls.append(name)
        raise script.UnknownOutcome("pending")

    monkeypatch.setattr(script, "perform", pending)
    with pytest.raises(script.UnknownOutcome):
        script.run_preflight(service, **inputs())
    assert calls == ["inventory_devices"]


def test_missing_device_exports_once_without_native_query(script, setup):
    service, runner, _, _ = setup("physical")
    values = inputs()
    values["unit_serial"] = "NOT-THE-DEVICE"
    with pytest.raises(ValueError, match="exactly one"):
        script.run_preflight(service, **values)
    assert [call[0] for call in runner.calls] == ["inventory_devices"]
    assert len(service.view()["exports"]["items"]) == 1


def test_cli_requires_power_flag_before_service_creation(script, monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("No service construction without explicit acknowledgement")

    monkeypatch.setattr(script, "ArrivalWizardService", forbidden)
    with pytest.raises(SystemExit):
        script.main(
            [
                "--vid",
                "10c4",
                "--pid",
                "ea60",
                "--usb-serial",
                "unit",
                "--reviewer",
                "test",
            ]
        )
