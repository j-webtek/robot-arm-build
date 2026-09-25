"""Exercise production ctypes call bodies with a wholly fake DLL.

The test-only hold replacement is paired with a fake WinDLL constructor before
any API call. No production release switch or native endpoint is used here.
"""

import ctypes
from dataclasses import replace

import pytest

from rocell.providers.windows import nonpurging_serial_api as native
from rocell.providers.windows.passive_serial_api import WindowsPassiveSerialApi


class Function:
    def __init__(self, name, dll):
        self.name, self.dll = name, dll

    def __call__(self, *args):
        self.dll.calls.append((self.name, args))
        return self.dll.handlers[self.name](*args)


class FakeDll:
    def __init__(self):
        self.calls, self.functions, self.handlers = [], {}, {}

    def __getattr__(self, name):
        if name not in self.functions:
            self.functions[name] = Function(name, self)
        return self.functions[name]


@pytest.fixture
def fixture(monkeypatch):
    dll = FakeDll()
    error = {"code": 0}
    monkeypatch.setattr(native.ctypes, "WinDLL", lambda *args, **kwargs: dll)
    monkeypatch.setattr(native.ctypes, "get_last_error", lambda: error["code"])
    monkeypatch.setattr(native, "_PINNED_NATIVE_IO", {})
    monkeypatch.setattr(native, "_native_release_hold", lambda: None)
    return WindowsPassiveSerialApi("COM4096"), dll, error


def test_exact_exclusive_overlapped_open_and_one_attempt(fixture):
    api, dll, _ = fixture
    dll.handlers["CreateFileW"] = lambda *args: 123
    assert api.create_file(r"\\.\COM4096") == 123
    assert dll.calls == [
        ("CreateFileW", (r"\\.\COM4096", 0xC0000000, 0, None, 3, 0x40000080, None))
    ]
    assert dll.CreateFileW.restype is ctypes.c_void_p
    with pytest.raises(native.NativeSerialError, match="ONE_USE"):
        api.create_file(r"\\.\COM4096")


def test_settings_are_marshaled_and_read_back_exactly(fixture):
    api, dll, _ = fixture
    stored = {}

    def save(key, size):
        def call(handle, pointer):
            stored[key] = ctypes.string_at(pointer, size)
            return 1

        return call

    def restore(key):
        def call(handle, pointer):
            ctypes.memmove(pointer, stored[key], len(stored[key]))
            return 1

        return call

    dll.handlers.update(
        SetCommState=save("dcb", ctypes.sizeof(native._DCB)),
        GetCommState=restore("dcb"),
        SetCommTimeouts=save("timeouts", ctypes.sizeof(native._TIMEOUTS)),
        GetCommTimeouts=restore("timeouts"),
    )
    api.set_state(123, native.DcbSettings())
    assert api.get_state(123) == native.DcbSettings()
    assert native._DCB.from_buffer_copy(stored["dcb"]).length == 28
    api.set_timeouts(123, native.CommTimeouts())
    assert api.get_timeouts(123) == native.CommTimeouts()
    before = len(dll.calls)
    with pytest.raises(native.NativeSerialError, match="UNREVIEWED_SETTINGS"):
        api.set_state(123, replace(native.DcbSettings(), flags=0x1001))
    assert len(dll.calls) == before


@pytest.mark.parametrize("completion_error", [0, 995, 258, 31])
def test_pending_read_completion_keeps_storage_until_terminal(
    fixture, completion_error
):
    api, dll, error = fixture
    token = native.IoToken(456, "read", 8)

    def read(handle, buffer, size, count, overlapped):
        ctypes.memmove(buffer, b"boot", 4)
        error["code"] = 997
        return 0

    def complete(handle, overlapped, count, timeout, alertable):
        assert alertable is False
        ctypes.cast(count, ctypes.POINTER(native._DWORD))[0] = 4
        error["code"] = completion_error
        return int(completion_error == 0)

    dll.handlers.update(
        ReadFile=read, GetOverlappedResultEx=complete, CancelIoEx=lambda *args: 1
    )
    assert api.submit_io(123, token).state == "PENDING"
    assert token.storage[1].hEvent == 456
    assert id(token) in native._PINNED_NATIVE_IO
    assert api.cancel_io(123, token) == "REQUESTED"
    # Cancellation is only a request; buffers must still be retained here.
    assert id(token) in native._PINNED_NATIVE_IO
    if completion_error == 31:
        with pytest.raises(native.NativeSerialError, match="COMPLETION_UNCONFIRMED"):
            api.complete_io(123, token, 100)
    else:
        result = api.complete_io(123, token, 100)
        assert (
            result.state
            == {0: "COMPLETE", 995: "ABORTED", 258: "PENDING"}[completion_error]
        )
        if completion_error == 0:
            assert result.data == b"boot" and result.transferred == 4
    assert (id(token) in native._PINNED_NATIVE_IO) == (completion_error in {258, 31})
    assert not any(name == "WriteFile" for name, _ in dll.calls)


def test_passive_query_rejected_before_dll_call(fixture):
    api, dll, _ = fixture
    token = native.IoToken(456, "write", len(native.FIXED_QUERY), native.FIXED_QUERY)
    with pytest.raises(native.NativeSerialError, match="PASSIVE_WRITES_FORBIDDEN"):
        api.submit_io(123, token)
    assert dll.calls == []
