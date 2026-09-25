"""Metadata discovery can precede powered feedback without a false power report."""

import pytest

from rocell.application.wizard_actions import ACTION_BY_ID, WizardError, validate_action_input
from test_wizard_native_arm_integration import setup, action, COUNTERS


def test_powered_metadata_public_workflow_has_no_device_effects(setup):
    service, _, _, _ = setup("physical")
    inventory = action(service, "inventory_devices", metadata_only=True)
    assert inventory["status"] == "SUCCEEDED"
    candidate = service.view()["device_selection"]["devices"]["SERIAL"]["candidates"][0]
    assert action(service, "review_arm_candidate", choice_id=candidate["choice_id"],
                  reviewer_id="fixture", metadata_only=True)["status"] == "SUCCEEDED"
    native = action(service, "inspect_native_arm_metadata", metadata_only=True)
    assert native["status"] == "SUCCEEDED"
    for operation in (inventory, native):
        assert all(operation["result"][key] == 0 for key in COUNTERS)
    assert service._powered_arm_startup is None


@pytest.mark.parametrize("name", ["inventory_devices", "inspect_native_arm_metadata"])
def test_unacknowledged_metadata_is_rejected(name):
    with pytest.raises(WizardError):
        validate_action_input(ACTION_BY_ID[name], {})
    values = validate_action_input(ACTION_BY_ID[name], {"metadata_only": True})
    assert values["power_disconnected"] is False
