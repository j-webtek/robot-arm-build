"""Exact owner tagging; metadata publication never falls back to another phase."""

from threading import RLock

import pytest

from rocell.application.physical_usb_identity_service import PhysicalUsbIdentityService


class Subject:
    def __init__(self, *, active=False, token=None):
        self.reconnect = {} if active else None
        self.reboot = self.attempt = None
        self.token = token
        self.calls = []
        self.fail = False

    def acquisition_started(self, *args):
        self.calls.append(("start", args))
        return self.token

    def acquisition_published(self, *args, **kwargs):
        self.calls.append(("publish", args, kwargs))
        if self.fail:
            raise ValueError("MODELED_PUBLICATION_REFUSED")


def owner(active):
    value = object.__new__(PhysicalUsbIdentityService)
    value._lock = RLock()
    value._trial = Subject(token={"baseline": True})
    value._reconnect = Subject(active=active, token={"reconnect": True})
    value._reboot = Subject()
    return value


def publish(value, token):
    value.acquisition_published(
        token, finished_at_ns=2, document={"modeled": True}, result_sha256="a" * 64
    )


@pytest.mark.parametrize("active", [False, True])
def test_only_active_phase_receives_start_and_successful_completion(active):
    value = owner(active)
    selected, other = (
        (value._reconnect, value._trial) if active else (value._trial, value._reconnect)
    )
    routed = value.acquisition_started("inventory_devices", "operation-1", 1)
    assert routed == {
        "phase": "AFTER_RECONNECT" if active else "BASELINE",
        "token": selected.token,
    }
    publish(value, routed)
    assert [c[0] for c in selected.calls] == ["start", "publish"]
    assert not other.calls


@pytest.mark.parametrize("active", [False, True])
def test_phase_change_between_start_and_completion_drops_old_token(active):
    value = owner(active)
    routed = value.acquisition_started("inventory_devices", "operation-1", 1)
    value._reconnect.reconnect = None if active else {}
    publish(value, routed)
    assert all(
        c[0] != "publish"
        for subject in (value._trial, value._reconnect)
        for c in subject.calls
    )


@pytest.mark.parametrize(
    "bad",
    [
        None,
        True,
        [],
        {},
        {"phase": "AFTER_RECONNECT"},
        {"phase": "BASELINE", "token": {}, "extra": True},
    ],
)
def test_missing_or_malformed_routing_tag_is_not_reinterpreted(bad):
    value = owner(True)
    publish(value, bad)
    assert not value._trial.calls and not value._reconnect.calls


def test_refused_reconnect_completion_does_not_publish_to_baseline():
    value = owner(True)
    routed = value.acquisition_started("inventory_devices", "operation-1", 1)
    value._reconnect.fail = True
    with pytest.raises(ValueError, match="MODELED_PUBLICATION_REFUSED"):
        publish(value, routed)
    assert not value._trial.calls


def test_phase_without_admissible_start_returns_no_token():
    value = owner(True)
    value._reconnect.token = None
    assert value.acquisition_started("inventory_devices", "operation-1", 1) is None
    assert not value._trial.calls
