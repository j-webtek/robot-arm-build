"""v13 campaign ceilings; modeled original ledgers, no device/provider access."""

import pytest

from rocell.application.physical_camera_session import PhysicalCameraSessionError
from rocell.application.physical_camera_usb_absence_readback import (
    read_original_usb_absence_campaigns,
)
from test_usb_reconnect_family_audit_boundary import audit_fixture


def read(tx, session):
    return read_original_usb_absence_campaigns(
        tx, session, _usb_reconnect_extension=True, _usb_reboot_extension=True
    )


def test_fourth_descriptor_is_only_available_through_closed_reboot_route(monkeypatch):
    tx, session, calls = audit_fixture(monkeypatch, 4)
    result = read(tx, session)
    assert len(result["identity"]) == 4 and result["presence"] == ()
    assert calls == ["scope", ("full_audit", True), "attempts", "attempts", "scope"]
    with pytest.raises(PhysicalCameraSessionError):
        read_original_usb_absence_campaigns(tx, session, _usb_reconnect_extension=True)


def test_fifth_descriptor_is_not_discarded_or_allowed(monkeypatch):
    tx, session, _ = audit_fixture(monkeypatch, 5)
    with pytest.raises(PhysicalCameraSessionError):
        read(tx, session)


@pytest.mark.parametrize("fault", ["changed_attempts", "audit_error"])
def test_reboot_keeps_whole_family_audit_and_final_attempt_check(monkeypatch, fault):
    tx, session, _ = audit_fixture(monkeypatch, 4, **{fault: True})
    with pytest.raises((PhysicalCameraSessionError, RuntimeError)):
        read(tx, session)


@pytest.mark.parametrize(
    "options",
    [
        {"_usb_reboot_extension": True},
        {"_usb_reconnect_extension": True, "_usb_reboot_extension": 1},
        {"_usb_reconnect_extension": True, "_usb_reboot_extension": None},
        {"_usb_reconnect_extension": 1, "_usb_reboot_extension": True},
    ],
)
def test_extension_flags_are_exact_and_reboot_requires_reconnect(monkeypatch, options):
    tx, session, calls = audit_fixture(monkeypatch, 1)
    with pytest.raises(PhysicalCameraSessionError):
        read_original_usb_absence_campaigns(tx, session, **options)
    assert not calls
