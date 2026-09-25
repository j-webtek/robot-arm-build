"""Coordinator result admission, independently of modeled service internals."""

from copy import deepcopy

import pytest

from rocell.application.arrival_wizard_service import ArrivalWizardService
from rocell.application.wizard_actions import WizardError


PREFIX = "physical_usb_reconnect_"


def result(kind, *, coverage="NO_DEVICE_IO", opens=0):
    action = PREFIX + kind
    report = dict(
        pending_completion_log=True, execution=None, usb_query_attempted=False
    )
    if kind == "boot_collect":
        report["host_boot"] = dict(
            schema="rocell.wizard_usb_reconnect_boot_summary.v1",
            original_state="BOOT_RETAINED",
            device_io_performed=False,
        )
    if kind == "collect":
        report.update(
            usb_query_attempted=True,
            execution=dict(
                schema="rocell.owned_usb_identity_run_summary.v1",
                physical_authority=False,
                hardware_qualified=False,
                counter_coverage=coverage,
                actual_counts=None if opens is None else dict(hub_open_attempts=opens),
                no_attempt=coverage == "NO_PROCESS_CREATED",
            ),
        )
    return dict(
        schema="rocell.wizard_usb_identity_action_result.v1",
        action_id=action,
        status="SUCCEEDED",
        steps=[dict(name=action, exit_code=0, report=report)],
        device_open_count=opens,
        serial_write_count=0,
        power_event_count=0,
        motion_command_count=0,
        contact_command_count=0,
        counter_coverage=coverage,
        physical_authority=False,
        hardware_qualified=False,
    )


def validate(value):
    ArrivalWizardService._validate_usb_identity_result(value["action_id"], value)


@pytest.mark.parametrize("kind", ("begin", "prepare", "review", "boot_collect"))
def test_file_and_boot_steps_cannot_claim_a_descriptor_attempt(kind):
    value = result(kind)
    before = deepcopy(value)
    validate(value)
    assert value == before
    for key, bad in (("usb_query_attempted", True), ("execution", {})):
        changed = deepcopy(value)
        changed["steps"][0]["report"][key] = bad
        with pytest.raises(WizardError, match="USB effect counts"):
            validate(changed)
    for opens in (True, 1, None):
        changed = deepcopy(value)
        changed["device_open_count"] = opens
        with pytest.raises(WizardError):
            validate(changed)


@pytest.mark.parametrize("state", ("BOOT_RETAINED", "BOOT_HELD", "BOOT_UNCERTAIN"))
def test_boot_completion_is_not_usb_or_camera_release(state):
    value = result("boot_collect")
    value["steps"][0]["report"]["host_boot"]["original_state"] = state
    validate(value)
    for key, bad in (
        ("original_state", "PASS"),
        ("device_io_performed", True),
        ("schema", "rocell.wizard_usb_absence_boot_summary.v1"),
    ):
        changed = deepcopy(value)
        changed["steps"][0]["report"]["host_boot"][key] = bad
        with pytest.raises(WizardError):
            validate(changed)


@pytest.mark.parametrize(
    "coverage,opens",
    (("NATIVE_RECEIPT", 3), ("NO_PROCESS_CREATED", 0), ("NOT_REPORTED", None)),
)
def test_query_retains_exact_native_zero_or_unknown_counts(coverage, opens):
    value = result("collect", coverage=coverage, opens=opens)
    before = deepcopy(value)
    validate(value)
    assert value == before
    changed = deepcopy(value)
    changed["device_open_count"] = 0 if opens is None else None
    with pytest.raises(WizardError):
        validate(changed)
    for bad in (False, None, 1):
        changed = deepcopy(value)
        changed["steps"][0]["report"]["usb_query_attempted"] = bad
        with pytest.raises(WizardError):
            validate(changed)


@pytest.mark.parametrize(
    "key",
    (
        "physical_authority",
        "hardware_qualified",
        "serial_write_count",
        "power_event_count",
        "motion_command_count",
        "contact_command_count",
    ),
)
def test_no_reconnect_result_can_grant_other_authority(key):
    value = result("collect", coverage="NATIVE_RECEIPT", opens=3)
    value[key] = True if key.endswith("authority") or key == "hardware_qualified" else 1
    with pytest.raises(WizardError):
        validate(value)


def test_lost_execution_record_cannot_be_replaced_by_clean_zero():
    value = result("collect")
    value["steps"][0]["report"].update(execution=None, usb_query_attempted=False)
    with pytest.raises(WizardError):
        validate(value)
