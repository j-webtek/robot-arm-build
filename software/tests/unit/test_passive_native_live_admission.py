"""Live-object admission tests; native DLL construction is always forbidden."""

from dataclasses import replace
import json
import time

import pytest

from rocell.application.passive_arm_preparation import prepare_attempt
from rocell.application.passive_arm_child_claim import claim_for_child
from rocell.providers.windows.passive_serial_api import WindowsPassiveSerialApi
from rocell.providers.windows.passive_serial_binding import PassiveSerialBinding
from rocell.providers.windows.nonpurging_serial_api import WindowsNativeSerialApi
from test_passive_arm_preparation import prepared_inputs
from test_wizard_native_arm_integration import setup

ORIGINAL_LOADER = WindowsNativeSerialApi._load_kernel


def admission(setup):
    _, _, values = prepared_inputs(setup)
    prepared = prepare_attempt(**values)
    receipt = prepared.journal.consume(now_monotonic_ns=time.monotonic_ns())
    claim = claim_for_child(
        root=values["root"],
        request=prepared.request,
        expected_consumption_sha256=receipt["consumption_sha256"],
        registration=values["registration"],
        now_monotonic_ns=time.monotonic_ns(),
    )
    original = json.loads(prepared.selection.payload)
    fresh = original["snapshot"]
    now = time.monotonic_ns()
    fresh["started_monotonic_ns"] = fresh["finished_monotonic_ns"] = now
    setup_raw = json.loads(
        (
            values["root"]
            / (values["setup_operation_id"] + "-passive-setup-original.json")
        ).read_bytes()
    )
    return dict(
        root=values["root"],
        claim=claim,
        request=prepared.request,
        binding=PassiveSerialBinding(prepared.selection),
        fresh_snapshot=fresh,
        generic_review=setup_raw["generic_review"],
        collection_not_before_ns=now,
        metadata_operation_id=values["attempt_id"],
    )


@pytest.fixture(autouse=True)
def no_dll(monkeypatch):
    from rocell.providers.windows.nonpurging_serial_api import WindowsNativeSerialApi

    def forbidden(*args, **kwargs):
        raise AssertionError("No DLL or real hardware in admission tests")

    # Filesystem durability legitimately uses kernel32. Forbid specifically the
    # serial loader, without disabling unrelated Windows file publication.
    monkeypatch.setattr(WindowsNativeSerialApi, "_load_kernel", forbidden)


def test_live_claim_admits_one_inert_exact_endpoint(setup):
    values = admission(setup)
    api = WindowsPassiveSerialApi.from_live_claim(**values)
    assert api.status()["passive_admission"] == "LIVE_CHILD_CLAIM_CONSUMED"
    assert api.status()["native_api_loaded"] is False
    assert api.expected_path == "\\\\.\\" + values["binding"].identity.port_name
    with pytest.raises(ValueError, match="Live unconsumed"):
        WindowsPassiveSerialApi.from_live_claim(**values)


def test_copied_claim_receipt_is_not_a_live_claim(setup):
    values = admission(setup)
    values["claim"] = replace(values["claim"])
    with pytest.raises(ValueError, match="Live unconsumed"):
        WindowsPassiveSerialApi.from_live_claim(**values)


def test_stale_identity_burns_claim_without_native_loading(setup):
    values = admission(setup)
    values["fresh_snapshot"]["finished_monotonic_ns"] -= 2_000_000_000
    with pytest.raises(ValueError):
        WindowsPassiveSerialApi.from_live_claim(**values)
    with pytest.raises(ValueError, match="Live unconsumed"):
        WindowsPassiveSerialApi.from_live_claim(**values)


def test_expiry_after_admission_blocks_open_without_dll(setup, monkeypatch):
    values = admission(setup)
    api = WindowsPassiveSerialApi.from_live_claim(**values)
    from rocell.providers.windows import passive_serial_api
    from rocell.providers.windows.nonpurging_serial_api import NativeSerialError

    later = values["fresh_snapshot"]["finished_monotonic_ns"] + 1_000_000_001
    monkeypatch.setattr(passive_serial_api.time, "monotonic_ns", lambda: later)
    with pytest.raises(NativeSerialError, match="PASSIVE_IDENTITY_EXPIRED"):
        api.create_file(api.expected_path)
    with pytest.raises(NativeSerialError, match="ONE_USE"):
        api.create_file(api.expected_path)


def test_admitted_api_loads_only_fake_dll_and_can_cleanup_after_deadline(
    setup, monkeypatch
):
    values = admission(setup)
    api = WindowsPassiveSerialApi.from_live_claim(**values)
    from test_passive_native_ctypes_calls import FakeDll
    from rocell.providers.windows import passive_serial_api
    import ctypes

    dll = FakeDll()
    dll.handlers.update(CreateFileW=lambda *args: 123, CloseHandle=lambda *args: 1)
    # Setup's durable file operations have finished. Restore only the serial
    # loader body and replace its DLL constructor with this incapable fixture.
    monkeypatch.setattr(ctypes, "WinDLL", lambda *args, **kwargs: dll)
    monkeypatch.setattr(WindowsNativeSerialApi, "_load_kernel", ORIGINAL_LOADER)
    assert api.create_file(api.expected_path) == 123
    assert api.status()["native_api_loaded"] is True
    expired = values["request"].to_dict()["parent_deadline_monotonic_ns"] + 1
    monkeypatch.setattr(passive_serial_api.time, "monotonic_ns", lambda: expired)
    api.close_handle(123)
    assert [name for name, _ in dll.calls] == ["CreateFileW", "CloseHandle"]
