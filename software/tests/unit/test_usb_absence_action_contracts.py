"""Pure public action/result boundaries, not an owned acquisition qualification.

The actual service envelope and Arrival validators run without setup, storage,
processes or devices. Execution summaries below are explicitly MODELED contract
inputs; full original evidence, effect and renderer joins have separate tests.
"""

from copy import deepcopy
from dataclasses import replace
import os
import subprocess
from types import SimpleNamespace

import pytest

from rocell.application import physical_usb_absence_service as absence
from rocell.application.arrival_wizard_service import ArrivalWizardService
from rocell.application.physical_usb_identity_service import PhysicalUsbIdentityService
from rocell.application.wizard_actions import (
    ACTIONS,
    ACTION_BY_ID,
    WizardError,
    validate_action_input,
)
from rocell.application.wizard_diagnostic_coordinator import (
    validate_diagnostic_worker_result,
)
from rocell.providers.windows import owned_usb_presence_runner
from rocell.providers.windows.host_boot_observation import WindowsHostBootObserver
from rocell.providers.windows.usb_presence_protocol import canonical


FORM_NAMES = {
    "physical_usb_absence_begin": (
        "operator_id",
        "confirm_unplug_report",
        "confirm_file_inspection",
    ),
    "physical_usb_absence_boot_review": ("reviewer_id", "confirm_exact_boot_scope"),
    "physical_usb_absence_boot_collect": (
        "confirm_boot_observation",
        "confirm_no_usb_query",
    ),
    "physical_usb_absence_runtime_review": (
        "reviewer_id",
        "confirm_policy_review",
        "confirm_runtime_review",
        "confirm_exact_target",
    ),
    "physical_usb_absence_collect": (
        "confirm_presence_query",
        "confirm_no_capture_or_arm",
    ),
}
TIMEOUTS = dict(zip(FORM_NAMES, (180, 120, 180, 120, 180)))
REPORT_FLAGS = (
    "physical_authority",
    "hardware_qualified",
    "camera_capture_authorized",
    "arm_access_authorized",
)


@pytest.fixture(autouse=True)
def no_processes_or_devices(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("Pure action contracts cannot launch a process or observe devices")

    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(os, "system", forbidden)
    monkeypatch.setattr(owned_usb_presence_runner, "_new_owner", forbidden)
    monkeypatch.setattr(WindowsHostBootObserver, "observe", forbidden)


def action_definition(action_id):
    # The public owner fields method is pure; construction/setup are not needed.
    owner = object.__new__(PhysicalUsbIdentityService)
    owner._absence = absence._UsbTrialAbsence(owner)
    return replace(ACTION_BY_ID[action_id], fields=owner.fields(action_id))


def accepted_values(action_id):
    return {
        field["name"]: (
            True if field["type"] == "checkbox" else "MODELED Procedural Label"
        )
        for field in action_definition(action_id).fields
    }


def modeled_summary(coverage="NATIVE_RECEIPT", *, calls=4):
    unknown = coverage == "NOT_REPORTED"
    no_process = coverage == "NO_PROCESS_CREATED"
    return dict(
        schema="rocell.owned_usb_presence_run_summary.v1",
        status="ABSENT" if coverage == "NATIVE_RECEIPT" else "FAILED",
        counter_coverage=coverage,
        no_attempt=no_process,
        actual_counts=(
            None
            if unknown
            else dict(
                api_calls=0 if no_process else calls,
                device_handle_opens=0,
                configuration_writes=0,
                frames=0,
            )
        ),
        physical_authority=False,
        hardware_qualified=False,
    )


def produced_result(action_id=absence.COLLECT, *, summary=None):
    """Run the real envelope producer around an explicitly modeled cached view."""
    owner = SimpleNamespace(
        _context=lambda: dict(provenance="MODELED_ACTION_CONTRACT_ONLY"),
        qualification_view=lambda: {},
    )
    subject = absence._UsbTrialAbsence(owner)
    evidence = (
        None
        if summary is None
        else SimpleNamespace(
            safe_summary=lambda: deepcopy(summary),
            observation=None,
        )
    )
    subject.execution = lambda: evidence
    subject.boot_summary = lambda: None
    subject.query_attempted = action_id == absence.COLLECT
    result = subject.result(action_id)
    assert owner._pending_result == canonical(result)
    assert owner._pending_action == action_id
    assert owner._publication == dict(status="PENDING", operation_id=None)
    return result


def validated(result):
    inert = object.__new__(ArrivalWizardService)
    return inert._validated_result(result["action_id"], result)


@pytest.mark.parametrize("action_id", FORM_NAMES)
def test_exact_catalog_forms_defaults_and_action_deadline(action_id):
    assert set(absence.ACTIONS) == set(FORM_NAMES)
    assert len([a for a in ACTIONS if a.action_id == action_id]) == 1
    action = action_definition(action_id)
    assert action.mode == "physical" and action.worker == "physical_usb_identity"
    assert action.section == "camera" and action.hold is None
    assert action.timeout_s == TIMEOUTS[action_id]
    assert tuple(field["name"] for field in action.fields) == FORM_NAMES[action_id]
    for field in action.fields:
        assert field["required"] is True
        if field["name"].startswith("confirm_"):
            assert set(field) == {"name", "type", "label", "required", "default"}
            assert field["type"] == "checkbox" and field["default"] is False
        else:
            assert set(field) == {
                "name",
                "type",
                "label",
                "required",
                "default",
                "max_length",
            }
            assert field["type"] == "text" and field["default"] == ""
            assert field["max_length"] == 64
    assert action.view(mode="physical", busy=False)["enabled"] is True
    assert action.view(mode="simulated", busy=False)["enabled"] is False
    assert action.view(mode="physical", busy=True)["enabled"] is False
    supplied = accepted_values(action_id)
    assert validate_action_input(action, supplied) == supplied
    with pytest.raises(WizardError):
        validate_action_input(action, {})
    detached = action.view(mode="physical", busy=False)
    detached["fields"][0]["default"] = "changed"
    assert action.fields[0]["default"] != "changed"


@pytest.mark.parametrize("action_id", FORM_NAMES)
@pytest.mark.parametrize("bad", (False, 0, 1, None, "true", []))
def test_confirmations_require_literal_true(action_id, bad):
    action = action_definition(action_id)
    supplied = accepted_values(action_id)
    name = next(f["name"] for f in action.fields if f["type"] == "checkbox")
    supplied[name] = bad
    with pytest.raises(WizardError) as error:
        validate_action_input(action, supplied)
    assert error.value.code == "CONFIRMATION_REQUIRED"


@pytest.mark.parametrize(
    "action_id", (absence.BEGIN, absence.BOOT_REVIEW, absence.RUNTIME_REVIEW)
)
@pytest.mark.parametrize("bad", ("", " ", "x" * 65, 5, None, "bad\x00actor"))
def test_actor_is_an_explicit_bounded_label(action_id, bad):
    action = action_definition(action_id)
    supplied = accepted_values(action_id)
    supplied[action.fields[0]["name"]] = bad
    with pytest.raises(WizardError) as error:
        validate_action_input(action, supplied)
    assert error.value.code == "INVALID_TEXT"


@pytest.mark.parametrize("action_id", FORM_NAMES)
@pytest.mark.parametrize(
    "name",
    (
        "endpoint",
        "physical_usb_instance_id",
        "argv",
        "runtime",
        "permit",
        "request_nonce",
        "physical_authority",
    ),
)
def test_input_cannot_supply_target_command_permit_or_authority(action_id, name):
    supplied = accepted_values(action_id)
    supplied[name] = "caller override"
    with pytest.raises(WizardError) as error:
        validate_action_input(action_definition(action_id), supplied)
    assert error.value.code == "UNKNOWN_INPUT_FIELD"


@pytest.mark.parametrize("action_id", tuple(FORM_NAMES)[:-1])
def test_file_or_boot_action_never_relabels_cached_query_effects(action_id):
    result = produced_result(action_id, summary=modeled_summary())
    assert result["presence_query_attempted"] is False
    assert result["counter_coverage"] == "NO_DEVICE_IO"
    assert result["device_open_count"] == result["presence_api_call_count"] == 0
    result_copy = validated(result)
    assert result_copy == result
    result["steps"][0]["report"]["execution"]["actual_counts"]["api_calls"] = 99
    assert (
        result_copy["steps"][0]["report"]["execution"]["actual_counts"]["api_calls"]
        == 4
    )


@pytest.mark.parametrize(
    "summary",
    (
        None,
        modeled_summary(),
        modeled_summary(calls=1),
        modeled_summary("NOT_REPORTED"),
        modeled_summary("NO_PROCESS_CREATED"),
    ),
)
def test_actual_query_envelope_preserves_known_unknown_and_no_process(summary):
    result = produced_result(summary=summary)
    assert validated(result) == result
    assert result["presence_query_attempted"] is True
    if summary is None or summary["counter_coverage"] == "NOT_REPORTED":
        assert result["presence_api_call_count"] is result["device_open_count"] is None
        assert result["counter_coverage"] == "NOT_REPORTED"
    else:
        assert (
            result["presence_api_call_count"] == summary["actual_counts"]["api_calls"]
        )
        assert (
            type(result["device_open_count"]) is int
            and result["device_open_count"] == 0
        )
    with pytest.raises(WizardError):
        validate_diagnostic_worker_result(
            result, action_id=absence.COLLECT, returncode=0
        )


@pytest.mark.parametrize(
    "key,bad",
    (
        ("schema", "rocell.wizard_worker_result.v1"),
        ("schema", "rocell.wizard_usb_identity_action_result.v1"),
        ("action_id", absence.BEGIN),
        ("status", "FAILED"),
        ("physical_authority", True),
        ("physical_authority", 0),
        ("hardware_qualified", True),
        ("hardware_qualified", 0),
        ("device_open_count", False),
        ("device_open_count", 1),
        ("device_open_count", None),
        ("presence_api_call_count", True),
        ("presence_api_call_count", 4.0),
        ("presence_api_call_count", 5),
        ("presence_api_call_count", -1),
        ("presence_api_call_count", None),
        ("presence_query_attempted", 1),
        ("presence_query_attempted", False),
        ("counter_coverage", "NO_DEVICE_IO"),
        ("counter_coverage", "NOT_REPORTED"),
        ("serial_write_count", 1),
        ("serial_write_count", False),
        ("power_event_count", 1),
        ("motion_command_count", 1),
        ("contact_command_count", 1),
        ("steps", []),
        ("steps", ()),
        ("unexpected", False),
    ),
)
def test_malformed_or_promoted_outer_result_rejected(key, bad):
    result = produced_result(summary=modeled_summary())
    result[key] = bad
    with pytest.raises(WizardError):
        ArrivalWizardService._validate_usb_absence_result(absence.COLLECT, result)


@pytest.mark.parametrize(
    "fault",
    (
        "name",
        "extra",
        "bool_exit",
        "nonzero_exit",
        "nonobject_report",
        "pending",
        *REPORT_FLAGS,
    ),
)
def test_step_identity_pending_and_authority_are_exact(fault):
    result = produced_result(summary=modeled_summary())
    step = result["steps"][0]
    if fault == "name":
        step["name"] = absence.BEGIN
    elif fault == "extra":
        step["extra"] = False
    elif fault in {"bool_exit", "nonzero_exit"}:
        step["exit_code"] = False if fault == "bool_exit" else 1
    elif fault == "nonobject_report":
        step["report"] = []
    elif fault == "pending":
        step["report"]["pending_completion_log"] = False
    else:
        step["report"][fault] = True
    with pytest.raises(WizardError):
        validated(result)


@pytest.mark.parametrize(
    "key,bad",
    (
        ("schema", "rocell.owned_usb_identity_run_summary.v1"),
        ("physical_authority", True),
        ("hardware_qualified", True),
        ("no_attempt", True),
        ("no_attempt", 0),
        ("counter_coverage", "NOT_REPORTED"),
        ("actual_counts", None),
        ("actual_counts", []),
    ),
)
def test_wrong_execution_summary_rejected(key, bad):
    result = produced_result(summary=modeled_summary())
    result["steps"][0]["report"]["execution"][key] = bad
    with pytest.raises(WizardError):
        validated(result)


@pytest.mark.parametrize(
    "key,bad",
    (
        ("api_calls", True),
        ("api_calls", False),
        ("api_calls", 4.0),
        ("api_calls", "4"),
        ("api_calls", -1),
        ("api_calls", 5),
        ("device_handle_opens", False),
        ("device_handle_opens", 1),
        ("configuration_writes", False),
        ("configuration_writes", 1),
        ("frames", False),
        ("frames", 1),
        ("extra", 0),
    ),
)
def test_native_counters_are_exact_integers_not_booleans(key, bad):
    result = produced_result(summary=modeled_summary())
    result["steps"][0]["report"]["execution"]["actual_counts"][key] = bad
    if key == "api_calls" and type(bad) is bool:
        # Equality alone accepts True==1 and False==0; require exact types.
        result["presence_api_call_count"] = int(bad)
    with pytest.raises(WizardError):
        validated(result)


@pytest.mark.parametrize(
    "key,bad",
    (
        ("presence_api_call_count", 0),
        ("device_open_count", 0),
        ("counter_coverage", "NO_PROCESS_CREATED"),
    ),
)
@pytest.mark.parametrize("with_summary", (False, True))
def test_missing_counts_never_become_zero(key, bad, with_summary):
    result = produced_result(
        summary=modeled_summary("NOT_REPORTED") if with_summary else None
    )
    result[key] = bad
    with pytest.raises(WizardError):
        validated(result)


@pytest.mark.parametrize(
    "fault",
    (
        "unknown_claims_no_attempt",
        "no_process_did_attempt",
        "no_process_calls",
        "no_process_boolean_calls",
    ),
)
def test_zero_is_supported_only_by_exact_no_process_summary(fault):
    unknown = fault == "unknown_claims_no_attempt"
    result = produced_result(
        summary=modeled_summary("NOT_REPORTED" if unknown else "NO_PROCESS_CREATED")
    )
    execution = result["steps"][0]["report"]["execution"]
    if unknown:
        execution["no_attempt"] = True
    elif fault == "no_process_did_attempt":
        execution["no_attempt"] = False
    elif fault == "no_process_calls":
        execution["actual_counts"]["api_calls"] = result["presence_api_call_count"] = 1
    else:
        execution["actual_counts"]["api_calls"] = False
    with pytest.raises(WizardError):
        validated(result)
