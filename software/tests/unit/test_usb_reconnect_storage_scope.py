"""Actual Setup guards with modeled originals; no M1 or hardware effect."""

from threading import Event

import pytest

from rocell.application import physical_camera_setup_service as setup
from rocell.application import physical_camera_usb_reconnect as reconnect
from rocell.application.wizard_actions import WizardError
from test_usb_phase_storage_deadline import (
    BusyProbe,
    modeled_scope,
    scope,
    START,
    SECOND,
)


@pytest.mark.parametrize(
    "delta", [1, 120 * SECOND, 121 * SECOND, 180 * SECOND, 180 * SECOND + 1]
)
def test_reconnect_uses_existing_180_second_outer_ceiling(monkeypatch, delta):
    owner = object.__new__(setup.PhysicalCameraSetupService)
    owner._operation_lock = probe = BusyProbe()
    monkeypatch.setattr(setup, "monotonic_ns", lambda: START)
    with pytest.raises(WizardError) as caught:
        with scope(owner, "usb_reconnect_transaction", Event(), START + delta):
            pytest.fail("Busy scope entered")
    assert caught.value.code == (
        "CAMERA_SETUP_BUSY"
        if delta <= 180 * SECOND
        else "INTAKE_STORAGE_CONTEXT_INVALID"
    )
    assert probe.calls == int(delta <= 180 * SECOND)


@pytest.mark.parametrize(
    "other",
    [
        "qualification",
        "static_contract",
        "received_camera",
        "camera_identity",
        "usb_identity",
        "usb_trial",
        "usb_phase",
        "usb_absence",
    ],
)
def test_reconnect_cannot_mix_with_any_other_storage_authority(monkeypatch, other):
    owner = object.__new__(setup.PhysicalCameraSetupService)
    owner._operation_lock = probe = BusyProbe()
    monkeypatch.setattr(setup, "monotonic_ns", lambda: START)
    options = dict(qualification=False, usb_reconnect=True)
    options[other] = True
    with pytest.raises(WizardError) as caught:
        with owner._source_transaction(
            cancellation=Event(),
            progress=lambda _: None,
            deadline_ns=START + SECOND,
            **options
        ):
            pytest.fail("Mixed storage authority entered")
    assert caught.value.code == "INTAKE_STORAGE_CONTEXT_INVALID" and probe.calls == 0


def configure(case, monkeypatch, state, *, current_launch=True):
    case.owner.launch_id = "wizard-" + "1" * 32
    phase = dict(
        state=state,
        phase="AFTER_RECONNECT",
        original_campaign=None,
        original_campaign_event=None,
        operator_event=dict(
            document=dict(
                launch_session_id=(
                    case.owner.launch_id if current_launch else "wizard-" + "2" * 32
                )
            )
        ),
    )
    case.workflow.update(
        schema="rocell.physical_camera_source_workflow_readback.v12",
        usb_qualification_reconnect=phase,
    )
    # Isolate actual Setup state checks. The real reader independently checks
    # complete stage/role/permit membership, not this simplified owner projection.
    monkeypatch.setattr(
        reconnect, "original_usb_reconnect_predecessor_v12", lambda _: {}
    )
    return phase


@pytest.mark.parametrize(
    "state,allowed",
    [
        ("PREPARATION_REQUESTED", True),
        ("PREPARED", True),
        ("REVIEWED", True),
        ("BOOT_RETAINED", True),
        ("BOOT_REQUESTED", False),
        ("BOOT_HELD", False),
        ("BOOT_UNCERTAIN", False),
        ("QUERY_REQUESTED", False),
        ("RETAINED_BLOCKED", False),
        ("INCOMPLETE", False),
        ("ORIGINAL_CAMPAIGN_HELD", False),
    ],
)
def test_only_exact_unused_original_boundaries_enter(
    modeled_scope, monkeypatch, state, allowed
):
    c = modeled_scope
    configure(c, monkeypatch, state)
    if allowed:
        deadline = START + 180 * SECOND
        with scope(c.owner, "usb_reconnect_transaction", c.cancellation, deadline):
            c.clock[0] = START + 121 * SECOND
        assert [r[0] for r in c.calls] == ["refresh", "read", "adopt"]
        assert c.calls[1][1]["deadline_ns"] == deadline
        assert c.owner._publication["status"] == "PENDING"
    else:
        with pytest.raises(WizardError) as caught:
            with scope(
                c.owner,
                "usb_reconnect_transaction",
                c.cancellation,
                START + 180 * SECOND,
            ):
                pytest.fail("Consumed or incomplete reconnect entered")
        assert caught.value.code == "USB_RECONNECT_ORIGINAL_REQUIRED" and not c.calls


@pytest.mark.parametrize(
    "kind", ["old_launch", "missing_report", "attempt", "attempt_event"]
)
def test_reopened_or_already_attempted_work_is_export_only(
    modeled_scope, monkeypatch, kind
):
    c = modeled_scope
    phase = configure(c, monkeypatch, "PREPARED", current_launch=kind != "old_launch")
    if kind == "missing_report":
        phase["operator_event"] = None
    elif kind == "attempt":
        phase["original_campaign"] = {}
    elif kind == "attempt_event":
        phase["original_campaign_event"] = {}
    with pytest.raises(WizardError) as caught:
        with scope(
            c.owner, "usb_reconnect_transaction", c.cancellation, START + 180 * SECOND
        ):
            pytest.fail("Historical attempt entered")
    assert caught.value.code == "USB_RECONNECT_ORIGINAL_REQUIRED" and not c.calls


def test_v11_begin_requires_real_predecessor_check(modeled_scope, monkeypatch):
    c = modeled_scope
    c.workflow["schema"] = "rocell.physical_camera_source_workflow_readback.v11"

    def refuse(_):
        raise ValueError("MODELED incomplete absence")

    monkeypatch.setattr(reconnect, "original_usb_reconnect_predecessor", refuse)
    with pytest.raises(WizardError) as caught:
        with scope(
            c.owner, "usb_reconnect_transaction", c.cancellation, START + 180 * SECOND
        ):
            pytest.fail("Unverified predecessor entered")
    assert caught.value.code == "USB_RECONNECT_ORIGINAL_REQUIRED" and not c.calls
