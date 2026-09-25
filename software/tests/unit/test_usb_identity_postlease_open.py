"""One owned open observation; later constructor checks remain independent.

Fresh isolated NTFS originals and modeled zero-I/O prerequisite subjects only.
The negative cases corrupt only their own temporary test originals. No native
worker, camera, COM port, hardware query or process is executed.
"""

import pytest

from rocell.application import commissioning_usb_identity_persistence as usb
from rocell.application import physical_onboarding_v2 as v2
from rocell.application.commissioning_m1_persistence import (
    M1CommissioningPersistenceError,
)
from test_commissioning_usb_identity import (
    SESSION,
    WINDOWS,
    actual_usb_fixture,
    no_device_calls,
)
from test_m1_fresh_snapshot_open import count_loads


pytestmark = WINDOWS


def observe_owned_construction(runtime, monkeypatch, loads, *, fault=None):
    """Count actual V2 loads between real lease activation and construction."""
    observed = dict(held=None, open_loads=None, constructor_loads=None, calls=0)
    activate = type(runtime._guard).activate
    constructor = usb.M1PhysicalUsbIdentityTransaction
    directory = runtime._session_path(SESSION)

    def corrupt():
        target = directory / (
            "header.json" if fault[1] == "header" else f"journal/{v2._HEAD_FILENAME}"
        )
        target.write_bytes(b"{isolated malformed test original}")

    def activated(guard, held, **kwargs):
        result = activate(guard, held, **kwargs)
        if guard is runtime._guard:
            observed["held"] = held
            loads.clear()
            if fault is not None and fault[0] == "after_lease":
                corrupt()
        return result

    def constructed(**kwargs):
        observed["calls"] += 1
        observed["open_loads"] = len(loads)
        before = len(loads)
        if fault is not None and fault[0] == "before_constructor":
            corrupt()
        result = constructor(**kwargs)
        observed["constructor_loads"] = len(loads) - before
        return result

    monkeypatch.setattr(type(runtime._guard), "activate", activated)
    monkeypatch.setattr(usb, "M1PhysicalUsbIdentityTransaction", constructed)
    return observed


def test_owned_open_uses_one_load_and_keeps_both_constructor_checks(
    tmp_path, monkeypatch
):
    runtime, _, _ = actual_usb_fixture(tmp_path)
    loads = count_loads(monkeypatch)
    observed = observe_owned_construction(runtime, monkeypatch, loads)
    with runtime.physical_usb_identity_transaction(SESSION) as transaction:
        assert observed["open_loads"] == 1
        assert observed["constructor_loads"] == 2
        assert observed["calls"] == 1 and not observed["held"].closed
        before = len(loads)
        snapshot = transaction.snapshot()
        assert len(loads) == before + 1
        assert snapshot.header.session_id == SESSION
    assert observed["held"].closed
    with pytest.raises(M1CommissioningPersistenceError, match="scope has ended"):
        transaction.snapshot()


@pytest.mark.parametrize("moment", ["after_lease", "before_constructor"])
@pytest.mark.parametrize("target", ["header", "head"])
def test_changed_original_still_refuses_and_releases_owned_scope(
    tmp_path, monkeypatch, moment, target
):
    runtime, _, _ = actual_usb_fixture(tmp_path)
    loads = count_loads(monkeypatch)
    observed = observe_owned_construction(
        runtime, monkeypatch, loads, fault=(moment, target)
    )
    with pytest.raises(v2.PhysicalOnboardingV2Error):
        with runtime.physical_usb_identity_transaction(SESSION):
            pytest.fail("changed originals must not publish a transaction")
    assert observed["held"] is not None and observed["held"].closed
    assert observed["calls"] == int(moment == "before_constructor")
    if moment == "before_constructor":
        assert observed["open_loads"] == 1
