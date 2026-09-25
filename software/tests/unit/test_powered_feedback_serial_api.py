"""Native facade tests with the serial DLL loader forbidden or replaced by a fake."""

from dataclasses import replace
import json
import time

import pytest

from rocell.application.passive_arm_identity import PassiveControllerSelection
from rocell.application.powered_feedback_child_claim import claim_for_child
from rocell.providers.windows.powered_feedback_binding import PoweredFeedbackBinding
from rocell.providers.windows.powered_feedback_serial_api import (
    WindowsPoweredFeedbackSerialApi,
)
from rocell.providers.windows.nonpurging_serial_api import (
    WindowsNativeSerialApi,
    NativeSerialError,
    IoToken,
    FIXED_QUERY,
    NATIVE_HOLD,
)
from test_powered_feedback_attempt_store import journal, consume
from test_wizard_native_arm_integration import setup

ORIGINAL_LOADER = WindowsNativeSerialApi._load_kernel


@pytest.fixture(autouse=True)
def no_serial_dll(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("No serial DLL or hardware in facade tests")

    monkeypatch.setattr(WindowsNativeSerialApi, "_load_kernel", forbidden)


def admission(setup):
    owner, values, prepared = journal(setup)
    receipt = consume(owner, values)
    claim = claim_for_child(
        root=values["root"],
        intent=prepared.intent,
        expected_consumption_sha256=receipt["consumption_sha256"],
        runtime_original=values["runtime_original"],
        current_source_sha256=values["current_source_sha256"],
        now_monotonic_ns=time.monotonic_ns(),
    )
    selection = PassiveControllerSelection(values["native_original"])
    fresh = json.loads(selection.payload)["snapshot"]
    now = time.monotonic_ns()
    fresh["started_monotonic_ns"] = fresh["finished_monotonic_ns"] = now
    return dict(
        root=values["root"],
        claim=claim,
        binding=PoweredFeedbackBinding(selection, prepared.intent),
        fresh_snapshot=fresh,
        collection_not_before_ns=now,
        metadata_operation_id=prepared.intent.to_dict()["attempt_id"],
        current_source_sha256=values["current_source_sha256"],
    )


def test_default_construction_stays_held_and_one_use():
    api = WindowsPoweredFeedbackSerialApi("COM91")
    with pytest.raises(NativeSerialError, match=NATIVE_HOLD):
        api.create_file(api.expected_path)
    with pytest.raises(NativeSerialError, match="ONE_USE"):
        api.create_file(api.expected_path)


def test_admission_is_inert_and_burns_exact_claim(setup):
    values = admission(setup)
    api = WindowsPoweredFeedbackSerialApi.from_live_claim(**values)
    assert api.status()["powered_admission"] == "LIVE_CHILD_CLAIM_CONSUMED"
    assert api.status()["native_api_loaded"] is False
    assert api.admitted_request_sha256 == values["binding"].intent.request_sha256
    with pytest.raises(ValueError, match="Live unconsumed"):
        WindowsPoweredFeedbackSerialApi.from_live_claim(**values)


def test_copied_claim_cannot_admit(setup):
    values = admission(setup)
    values["claim"] = replace(values["claim"])
    with pytest.raises(ValueError, match="Live unconsumed"):
        WindowsPoweredFeedbackSerialApi.from_live_claim(**values)


def test_stale_identity_burns_claim(setup):
    values = admission(setup)
    values["fresh_snapshot"]["finished_monotonic_ns"] -= 2_000_000_000
    with pytest.raises(ValueError):
        WindowsPoweredFeedbackSerialApi.from_live_claim(**values)
    with pytest.raises(ValueError, match="Live unconsumed"):
        WindowsPoweredFeedbackSerialApi.from_live_claim(**values)


@pytest.mark.parametrize("method", ["submit_io", "complete_io", "cancel_io"])
def test_movement_payload_is_rejected_before_loader(method):
    api = WindowsPoweredFeedbackSerialApi("COM91")
    raw = b'{"T":100}\n'
    token = IoToken(1, "write", len(raw), raw)
    args = (1, token, 0) if method == "complete_io" else (1, token)
    with pytest.raises(NativeSerialError, match="UNREVIEWED_IO"):
        getattr(api, method)(*args)


def test_failed_first_write_cannot_retry():
    api = WindowsPoweredFeedbackSerialApi("COM91")
    with pytest.raises(NativeSerialError, match=NATIVE_HOLD):
        api.submit_io(1, IoToken(1, "write", len(FIXED_QUERY), FIXED_QUERY))
    with pytest.raises(NativeSerialError, match="ONE_QUERY_NO_RETRY"):
        api.submit_io(1, IoToken(2, "write", len(FIXED_QUERY), FIXED_QUERY))


def test_fake_dll_open_then_cleanup_after_deadline(setup, monkeypatch):
    import ctypes
    from test_passive_native_ctypes_calls import FakeDll
    from rocell.providers.windows import powered_feedback_serial_api as module

    values = admission(setup)
    api = WindowsPoweredFeedbackSerialApi.from_live_claim(**values)
    dll = FakeDll()
    dll.handlers.update(CreateFileW=lambda *args: 123, CloseHandle=lambda *args: 1)
    monkeypatch.setattr(ctypes, "WinDLL", lambda *args, **kwargs: dll)
    monkeypatch.setattr(WindowsNativeSerialApi, "_load_kernel", ORIGINAL_LOADER)
    assert api.create_file(api.expected_path) == 123
    monkeypatch.setattr(
        module.time,
        "monotonic_ns",
        lambda: values["binding"].intent.to_dict()["parent_deadline_monotonic_ns"] + 1,
    )
    api.close_handle(123)
    assert [name for name, _ in dll.calls] == ["CreateFileW", "CloseHandle"]


def test_live_loop_requires_admission_and_precancel_opens_nothing(setup):
    from threading import Event
    from rocell.providers.windows.powered_feedback_observation import observe_physical
    from rocell.providers.windows.nonpurging_serial_api import IncapableWin32SerialApi
    from rocell.providers.windows.nonpurging_serial_backend import (
        NonPurgingSerialConnection,
    )

    values = admission(setup)
    binding = values["binding"]
    with pytest.raises(ValueError, match="live-claim-admitted"):
        observe_physical(binding, IncapableWin32SerialApi(), Event())
    with pytest.raises(NativeSerialError, match="POWERED_FEEDBACK_PHYSICAL_HELD"):
        NonPurgingSerialConnection(
            binding, api=WindowsPoweredFeedbackSerialApi(binding.identity.port_name)
        )
    api = WindowsPoweredFeedbackSerialApi.from_live_claim(**values)
    cancel = Event()
    cancel.set()
    result = observe_physical(binding, api, cancel)
    assert result["status"] == "FAILED"
    assert result["errors"] == ["CANCELLED"]
    assert result["lifecycle"]["resource_counts"]["acquired"] == 0
    assert result["lifecycle"]["composition"] == "WINDOWS_POWERED_FEEDBACK_ENGINEERING"
    assert api.status()["native_api_loaded"] is False


@pytest.mark.parametrize("kind", ["read", "write"])
@pytest.mark.parametrize("immediate", [False, True])
@pytest.mark.parametrize("abort", [False, True])
def test_fake_native_submitted_token_can_complete_or_cancel(
    setup, monkeypatch, kind, immediate, abort
):
    """Regression for received-unit REUSED_IO_TOKEN; never opens a real port."""
    import ctypes
    from rocell.providers.windows import nonpurging_serial_api as native
    from test_passive_native_ctypes_calls import FakeDll

    values = admission(setup)
    api = WindowsPoweredFeedbackSerialApi.from_live_claim(**values)
    dll, error = FakeDll(), {"code": 0}
    monkeypatch.setattr(ctypes, "WinDLL", lambda *a, **kw: dll)
    monkeypatch.setattr(ctypes, "get_last_error", lambda: error["code"])
    monkeypatch.setattr(native, "_PINNED_NATIVE_IO", {})
    monkeypatch.setattr(WindowsNativeSerialApi, "_load_kernel", ORIGINAL_LOADER)
    payload = FIXED_QUERY if kind == "write" else b""
    token = IoToken(456, kind, len(FIXED_QUERY), payload)

    def submit(*args):
        error["code"] = 997
        return int(immediate)

    def complete(handle, overlapped, count, timeout, alertable):
        ctypes.cast(count, ctypes.POINTER(native._DWORD))[0] = token.size
        error["code"] = 995 if abort else 0
        return int(not abort)

    dll.handlers.update(ReadFile=submit, WriteFile=submit,
                        GetOverlappedResultEx=complete, CancelIoEx=lambda *args: 1)
    result = api.submit_io(123, token)
    if not immediate:
        assert result.state == "PENDING"
        # Foreign/copy tokens must not gain access to the pending buffer.
        with pytest.raises(NativeSerialError, match="UNOWNED_PENDING_IO"):
            api.complete_io(123, replace(token), 0)
        assert api.cancel_io(123, token) == "REQUESTED"
        assert id(token) in native._PINNED_NATIVE_IO
        result = api.complete_io(123, token, 100)
    assert result.state == ("ABORTED" if abort else "COMPLETE")
    assert not native._PINNED_NATIVE_IO
    with pytest.raises(NativeSerialError, match="UNOWNED_PENDING_IO"):
        api.complete_io(123, token, 0)
    with pytest.raises(NativeSerialError, match="REUSED_IO_TOKEN"):
        api.submit_io(123, token)
