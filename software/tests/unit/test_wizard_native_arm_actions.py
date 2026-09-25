"""Closed UI/IPC contract tests; no host inventory or device entry points."""

from copy import deepcopy

import pytest

from rocell.application.wizard_actions import (
    ACTION_BY_ID,
    WizardError,
    validate_action_input,
)
from rocell.application.wizard_diagnostic_coordinator import (
    validate_diagnostic_worker_result,
)


@pytest.mark.parametrize(
    "action_id", ["inspect_native_arm_metadata", "rehearse_native_arm_metadata"]
)
def test_explicit_checkboxes_and_closed_modes(action_id):
    action = ACTION_BY_ID[action_id]
    assert action.timeout_s == 20
    assert action.section == "arm"
    assert all(
        field["default"] is False
        for field in action.fields
        if field["type"] == "checkbox"
    )
    with pytest.raises(WizardError):
        validate_action_input(action, {})
    assert not action.view(
        mode="physical" if action.mode == "rehearsal" else "rehearsal", busy=False
    )["enabled"]


@pytest.mark.parametrize(
    "field",
    ["port", "path", "command", "firmware", "_arm_review_sha256", "physical_authority"],
)
def test_no_operator_supplied_transport_or_internal_context(field):
    with pytest.raises(WizardError):
        validate_action_input(
            ACTION_BY_ID["inspect_native_arm_metadata"],
            {
                "power_disconnected": True,
                "metadata_only": True,
                field: "invented",
            },
        )


@pytest.mark.parametrize(
    "action_id,metadata",
    [
        ("inspect_native_arm_metadata", True),
        ("rehearse_native_arm_metadata", False),
    ],
)
def test_worker_envelope_requires_correct_metadata_effect(action_id, metadata):
    result = {
        "schema": "rocell.wizard_worker_result.v1",
        "action_id": action_id,
        "status": "SUCCEEDED",
        "steps": [
            {"name": "native_arm_metadata_snapshot", "exit_code": 0, "report": {}}
        ],
        "device_open_count": 0,
        "serial_write_count": 0,
        "power_event_count": 0,
        "motion_command_count": 0,
        "contact_command_count": 0,
        "metadata_inventory_performed": metadata,
        "physical_authority": False,
    }
    assert (
        validate_diagnostic_worker_result(result, action_id=action_id, returncode=0)
        == result
    )
    changed = deepcopy(result)
    changed["metadata_inventory_performed"] = not metadata
    with pytest.raises(WizardError):
        validate_diagnostic_worker_result(changed, action_id=action_id, returncode=0)
    for field in (
        "device_open_count",
        "serial_write_count",
        "power_event_count",
        "motion_command_count",
        "contact_command_count",
    ):
        changed = deepcopy(result)
        changed[field] = 1
        with pytest.raises(WizardError):
            validate_diagnostic_worker_result(
                changed, action_id=action_id, returncode=0
            )
