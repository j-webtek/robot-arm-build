"""Real Setup guards with modeled context; no M1/process/device effects."""

from threading import Event
import pytest
from rocell.application import physical_camera_setup_service as setup_impl
from rocell.application import physical_camera_usb_absence as absence
from rocell.application.wizard_actions import WizardError
from test_usb_phase_storage_deadline import (
    BusyProbe,
    modeled_scope,
    scope,
    START,
    SECOND,
)


@pytest.mark.parametrize(
    "delta", [1, 120 * SECOND, 120 * SECOND + 1, 180 * SECOND, 180 * SECOND + 1]
)
def test_exact_absence_storage_180_ceiling(monkeypatch, delta):
    owner = setup_impl.PhysicalCameraSetupService.__new__(
        setup_impl.PhysicalCameraSetupService
    )
    owner._operation_lock = probe = BusyProbe()
    monkeypatch.setattr(setup_impl, "monotonic_ns", lambda: START)
    with pytest.raises(WizardError) as caught:
        with scope(owner, "usb_absence_transaction", Event(), START + delta):
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
    ],
)
def test_mixed_absence_flags_do_not_extend_other_scope(monkeypatch, other):
    owner = setup_impl.PhysicalCameraSetupService.__new__(
        setup_impl.PhysicalCameraSetupService
    )
    owner._operation_lock = probe = BusyProbe()
    monkeypatch.setattr(setup_impl, "monotonic_ns", lambda: START)
    options = dict(qualification=False, usb_absence=True)
    options[other] = True
    with pytest.raises(WizardError) as caught:
        with owner._source_transaction(
            cancellation=Event(),
            progress=lambda _: None,
            deadline_ns=START + 121 * SECOND,
            **options
        ):
            pytest.fail("Mixed flags entered")
    assert probe.calls == 0 and caught.value.code == "INTAKE_STORAGE_CONTEXT_INVALID"


@pytest.mark.parametrize(
    "state,allowed",
    [
        ("PREPARED", True),
        ("BOOT_REVIEWED", True),
        ("PRESENCE_REVIEW_PREPARED", True),
        ("RUNTIME_REVIEWED", True),
        ("QUERY_REQUESTED", False),
        ("PRESENCE_REVIEW_REQUESTED", False),
        ("BOOT_REQUESTED", False),
        ("BOOT_HELD", False),
        ("BOOT_UNCERTAIN", False),
        ("INCOMPLETE", False),
        ("RETAINED_BLOCKED", False),
    ],
)
def test_setup_requires_unused_exact_absence_boundary(
    modeled_scope, monkeypatch, state, allowed
):
    c = modeled_scope
    c.workflow.update(
        schema="rocell.physical_camera_source_workflow_readback.v11",
        usb_qualification_absence={"state": state},
    )
    # This test isolates entry state; full baseline authentication is independently
    # covered by the original reader tests rather than fabricating original bytes.
    monkeypatch.setattr(absence, "original_usb_absence_baseline", lambda _: {})
    if allowed:
        with scope(
            c.owner, "usb_absence_transaction", c.cancellation, START + 180 * SECOND
        ):
            pass
        assert [x[0] for x in c.calls] == ["refresh", "read", "adopt"]
    else:
        with pytest.raises(WizardError) as caught:
            with scope(
                c.owner, "usb_absence_transaction", c.cancellation, START + 180 * SECOND
            ):
                pytest.fail("Replayed original")
        assert caught.value.code == "USB_ABSENCE_ORIGINAL_REQUIRED" and not c.calls


@pytest.mark.parametrize(
    "deadline", [None, True, START, START - 1, float(START + SECOND)]
)
def test_invalid_absence_deadline_before_lock(monkeypatch, deadline):
    owner = setup_impl.PhysicalCameraSetupService.__new__(
        setup_impl.PhysicalCameraSetupService
    )
    owner._operation_lock = probe = BusyProbe()
    monkeypatch.setattr(setup_impl, "monotonic_ns", lambda: START)
    with pytest.raises(WizardError):
        with scope(owner, "usb_absence_transaction", Event(), deadline):
            pytest.fail("Invalid deadline")
    assert not probe.calls
