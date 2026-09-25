"""No application construction: smoke-harness cleanup and closed action tests."""

import importlib.util
from pathlib import Path
import sys

import pytest


def load_script():
    path = (
        Path(__file__).resolve().parents[2]
        / "scripts/wizard_native_arm_metadata_smoke.py"
    )
    spec = importlib.util.spec_from_file_location("native_arm_smoke_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_main_uses_real_service_shutdown_method_on_validation_failure(monkeypatch):
    script = load_script()
    calls = []

    class IncapableService:
        def __init__(self, *args, **kwargs):
            calls.append("constructed")

        def view(self):
            raise ValueError("injected pre-action failure")

        def shutdown(self):
            calls.append("shutdown")

    monkeypatch.setattr(script, "ArrivalWizardService", IncapableService)
    monkeypatch.setattr(script, "source_fingerprint", lambda _: "a" * 64)
    monkeypatch.setattr(sys, "argv", ["smoke", "--source", "a" * 64])
    with pytest.raises(ValueError, match="injected pre-action failure"):
        script.main()
    assert calls == ["constructed", "shutdown"]


@pytest.mark.parametrize(
    "action_id",
    [
        "inspect_native_arm_metadata",
        "inventory_devices",
        "arm_connect",
        "physical_camera_probe",
    ],
)
def test_harness_refuses_all_real_device_or_inventory_actions(action_id):
    script = load_script()
    with pytest.raises(ValueError, match="fixed incapable"):
        script.action(None, action_id, {})
