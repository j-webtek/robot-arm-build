"""Closed parent USB result boundary; no process, metadata query or device access."""

from copy import deepcopy

import pytest

from rocell.application.arrival_wizard_service import ArrivalWizardService
from rocell.application.wizard_actions import ACTION_BY_ID, WizardError
from rocell.application.wizard_diagnostic_coordinator import (
    validate_diagnostic_worker_result,
)
from test_arrival_wizard_service import make_service, _ticket


def result(
    *, coverage="NATIVE_RECEIPT", opens=1, action="physical_usb_identity_collect"
):
    execution = dict(
        schema="rocell.owned_usb_identity_run_summary.v1",
        counter_coverage=coverage,
        no_attempt=coverage == "NO_PROCESS_CREATED",
        actual_counts=None if opens is None else {"hub_open_attempts": opens},
        physical_authority=False,
        hardware_qualified=False,
    )
    return dict(
        schema="rocell.wizard_usb_identity_action_result.v1",
        action_id=action,
        status="SUCCEEDED",
        steps=[
            dict(
                name=action,
                exit_code=0,
                report=dict(execution=execution, pending_completion_log=True),
            )
        ],
        device_open_count=opens,
        serial_write_count=0,
        power_event_count=0,
        motion_command_count=0,
        contact_command_count=0,
        counter_coverage=coverage,
        physical_authority=False,
        hardware_qualified=False,
    )


@pytest.mark.parametrize(
    "coverage,opens",
    [("NATIVE_RECEIPT", 1), ("NOT_REPORTED", None), ("NO_PROCESS_CREATED", 0)],
)
def test_parent_counts_do_not_weaken_the_diagnostic_child(coverage, opens):
    value = result(coverage=coverage, opens=opens)
    ArrivalWizardService._validate_usb_identity_result(value["action_id"], value)
    with pytest.raises(WizardError):
        validate_diagnostic_worker_result(
            value, action_id=value["action_id"], returncode=0
        )


@pytest.mark.parametrize(
    "change",
    [
        lambda v: v.update(device_open_count=0),
        lambda v: v.update(device_open_count=None),
        lambda v: v.update(device_open_count=True),
        lambda v: v.update(device_open_count=33),
        lambda v: v.update(serial_write_count=1),
        lambda v: v.update(physical_authority=True),
        lambda v: v.update(hardware_qualified=True),
        lambda v: v.update(metadata_inventory_performed=False),
        lambda v: v.update(counter_coverage="NO_DEVICE_IO"),
        lambda v: v["steps"][0]["report"].update(pending_completion_log=False),
        lambda v: v["steps"][0].update(name="other_action"),
        lambda v: v["steps"][0]["report"].update(execution=None),
    ],
)
def test_bad_effectful_results_cannot_claim_success(change):
    value = result()
    change(value)
    with pytest.raises(WizardError):
        ArrivalWizardService._validate_usb_identity_result(value["action_id"], value)


@pytest.mark.parametrize("suffix", ["inspect", "review", "export"])
def test_file_action_reports_own_zero_effects_not_previous_query_counts(suffix):
    action = "physical_usb_identity_" + suffix
    value = result(action=action)
    value.update(device_open_count=0, counter_coverage="NO_DEVICE_IO")
    ArrivalWizardService._validate_usb_identity_result(action, value)
    bad = deepcopy(value)
    bad["device_open_count"] = 1
    with pytest.raises(WizardError):
        ArrivalWizardService._validate_usb_identity_result(action, bad)


def test_four_actions_are_real_service_worker_with_separate_campaign_budget():
    for suffix, timeout in (
        ("inspect", 120),
        ("review", 120),
        ("collect", 180),
        ("export", 120),
    ):
        action = ACTION_BY_ID["physical_usb_identity_" + suffix]
        assert action.worker == "physical_usb_identity" and action.hold is None
        assert action.timeout_s == timeout and action.mode == "physical"


@pytest.mark.parametrize("owner_name", ["source", "static", "received"])
def test_v8_cached_adoption_keeps_older_subject_publication_historical(owner_name):
    """Only exercise cached adoption branch, not claim this modeled prefix is M1."""
    from threading import RLock
    from types import SimpleNamespace
    from rocell.application.physical_source_qualification_service import (
        PhysicalSourceQualificationService,
    )
    from rocell.application.physical_static_camera_onboarding_service import (
        PhysicalStaticCameraOnboardingService,
    )
    from rocell.application.physical_received_camera_service import (
        PhysicalReceivedCameraService,
    )

    kind = dict(
        source=PhysicalSourceQualificationService,
        static=PhysicalStaticCameraOnboardingService,
        received=PhysicalReceivedCameraService,
    )[owner_name]
    owner = object.__new__(kind)
    owner._lock = RLock()
    owner._pending_draft = None
    owner.setup = SimpleNamespace(
        view=lambda: {
            "publication": {"status": "CURRENT", "operation_id": "logged-readback"}
        }
    )
    original = {
        "schema": "rocell.physical_camera_source_workflow_readback.v8",
        "modeled_prefix": "unchanged original subject",
    }
    calls = []

    def adopt():
        calls.append("cached-adopt")
        owner._workflow = deepcopy(original)

    owner._adopt = adopt
    owner.observe_setup()
    assert calls == ["cached-adopt"]
    assert owner._publication == {"status": "HISTORICAL_HELD", "operation_id": None}
    assert owner._workflow == original and owner._pending_result is None


def test_public_usb_previews_use_explicit_consents_and_never_construct_dispatch(
    make_service, monkeypatch
):
    from rocell.application import physical_usb_identity_service as module

    service, runner, _ = make_service(mode="physical")
    owner = service._usb_identity
    monkeypatch.setattr(owner, "blocked_reason", lambda action, **context: None)
    monkeypatch.setattr(
        module,
        "PhysicalUsbIdentityDispatchOwner",
        lambda *a, **kw: pytest.fail("dispatch from preview"),
    )
    before = deepcopy(owner.view())
    ticket = _ticket(
        service,
        module.INSPECT,
        dict(operator_id="Operator label with spaces", confirm_file_inspection=True),
    )
    assert ticket["input"]["operator_id"] == "Operator label with spaces"
    assert "File-only" in " ".join(ticket["effects"])
    collect = _ticket(
        service,
        module.COLLECT,
        dict(confirm_usb_query=True, confirm_no_capture_or_arm=True),
    )
    effects = " ".join(collect["effects"])
    assert (
        "up to 25 seconds bounded by the original permit expiry" in effects
        and "full prepared 20-second lifecycle must still fit" in effects
        and "Hub queries are device effects" in effects
    )
    assert (
        "no automatic retry" in effects.lower()
        and "Unknown counts remain unknown" in effects
    )
    for values in (
        dict(confirm_usb_query=False, confirm_no_capture_or_arm=True),
        dict(confirm_usb_query=True, confirm_no_capture_or_arm=False),
    ):
        with pytest.raises(WizardError):
            _ticket(service, module.COLLECT, values)
    assert (
        owner.view() == before and service._primary_operations == 0 and not runner.calls
    )
