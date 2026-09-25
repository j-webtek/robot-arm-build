"""Narrow Win32 serial call boundary; actual native access is unreleased.

The memory facade executes no Windows calls. The native facade contains the
ctypes call implementation but is source-held before loading a DLL. Neither
facade is a commissioning authorizer or a general application transport.
"""

from __future__ import annotations

import ctypes
from dataclasses import dataclass, replace
import os
import re
from typing import Any, Protocol


NATIVE_HOLD = "NONPURGING_SERIAL_INDEPENDENT_PHYSICAL_QUALIFICATION_REQUIRED"
FIXED_QUERY = b'{"T":105}\n'
MAX_IO_BYTES = 65537
MAX_CALLS = 32768


class NativeSerialError(RuntimeError):
    """Bounded diagnostics deliberately exclude vendor/driver exception text."""

    def __init__(self, code: str, operation: str, winerror: int = 0) -> None:
        super().__init__(f"{code}: {operation}")
        self.code = code
        self.operation = operation
        self.winerror = winerror


def _int(value: object, low: int, high: int, name: str) -> int:
    if type(value) is not int or not low <= value <= high:
        raise NativeSerialError("INVALID_ARGUMENT", name)
    return value


def _validate_com_path(path: str) -> None:
    if (
        type(path) is not str
        or re.fullmatch(r"\\\\\.\\COM[1-9][0-9]{0,3}", path) is None
    ):
        raise NativeSerialError("EXACT_COM_PATH_REQUIRED", "create_file")
    if int(path[7:]) > 4096:
        raise NativeSerialError("EXACT_COM_PATH_REQUIRED", "create_file")


@dataclass(frozen=True, slots=True)
class DcbSettings:
    """Reviewed DCB values, not browser-settable serial options.

    Only fBinary is set in flags. This disables parity/flow control, RTS/DTR,
    DSR filtering, null removal, error substitution, and abort-on-error.
    Distinct XON/XOFF characters remain necessary to SetCommState's contract
    even with software flow control disabled.
    """

    baud_rate: int = 115200
    flags: int = 1
    byte_size: int = 8
    parity: int = 0
    stop_bits: int = 0
    xon_limit: int = 128
    xoff_limit: int = 128
    xon_char: int = 17
    xoff_char: int = 19
    error_char: int = 0
    eof_char: int = 0
    event_char: int = 0


@dataclass(frozen=True, slots=True)
class CommTimeouts:
    read_interval_ms: int = 0
    read_multiplier_ms: int = 0
    read_constant_ms: int = 1000
    write_multiplier_ms: int = 0
    write_constant_ms: int = 1000


@dataclass(frozen=True, slots=True)
class QueueStatus:
    input_bytes: int
    output_bytes: int = 0
    error_mask: int = 0


@dataclass(frozen=True, slots=True)
class IoCompletion:
    state: str  # COMPLETE, PENDING, ABORTED, FAILED
    transferred: int = 0
    data: bytes = b""
    winerror: int = 0


@dataclass(slots=True)
class IoToken:
    """Keep this token, native buffer and OVERLAPPED alive until completion."""

    event: int
    kind: str
    size: int
    payload: bytes = b""
    storage: Any = None
    submitted: bool = False
    cancelled: bool = False
    completion: IoCompletion | None = None


def validate_native_io_shape(token: IoToken) -> None:
    """Validate the fixed I/O vocabulary without assuming a fresh submission."""
    if type(token) is not IoToken:
        raise NativeSerialError("INVALID_IO_TOKEN", "io_token")
    _int(token.event, 1, (1 << (ctypes.sizeof(ctypes.c_void_p) * 8)) - 2, "io_event")
    _int(token.size, 1, MAX_IO_BYTES, "io_size")
    if type(token.kind) is not str or token.kind not in ("read", "write"):
        raise NativeSerialError("UNREVIEWED_IO", "io_kind")
    if type(token.payload) is not bytes:
        raise NativeSerialError("UNREVIEWED_IO", "io_payload")
    if token.kind == "write" and (
        token.payload != FIXED_QUERY or token.size != len(FIXED_QUERY)
    ):
        raise NativeSerialError("UNREVIEWED_IO", "io_write")
    if token.kind == "read" and token.payload:
        raise NativeSerialError("UNREVIEWED_IO", "io_read")


def validate_native_io_token(token: IoToken) -> None:
    """Pure validation before allocating/copying a new native buffer."""
    validate_native_io_shape(token)
    if (
        token.submitted is not False
        or token.cancelled is not False
        or token.storage is not None
        or token.completion is not None
    ):
        raise NativeSerialError("REUSED_IO_TOKEN", "io_token")


def validate_owned_pending_io(api: object, token: IoToken) -> None:
    """Completion/cancellation must use the exact still-pinned owner's token.

    A submitted token is expected here, not a forbidden resubmission. Keep the
    buffer pinned until the native completion routine proves it terminal.
    """
    validate_native_io_shape(token)
    owned = _PINNED_NATIVE_IO.get(id(token))
    if owned is None or owned[0] is not api or owned[1] is not token:
        raise NativeSerialError("UNOWNED_PENDING_IO", "io_token")


class Win32SerialApi(Protocol):
    """Narrow injectable seam; no purge, reset, setup-buffer or flush method."""

    def create_file(self, path: str) -> int: ...
    def create_event(self) -> int: ...
    def get_state(self, handle: int) -> DcbSettings: ...
    def set_state(self, handle: int, settings: DcbSettings) -> None: ...
    def get_timeouts(self, handle: int) -> CommTimeouts: ...
    def set_timeouts(self, handle: int, settings: CommTimeouts) -> None: ...
    def queue_status(self, handle: int) -> QueueStatus: ...
    def submit_io(self, handle: int, token: IoToken) -> IoCompletion: ...
    def complete_io(
        self, handle: int, token: IoToken, timeout_ms: int
    ) -> IoCompletion: ...
    def cancel_io(self, handle: int, token: IoToken) -> str: ...
    def close_handle(self, handle: int) -> None: ...


@dataclass(frozen=True, slots=True)
class IncapableWin32Scenario:
    """Finite, memory-only outcomes. No callback or foreign handle injection."""

    startup_bytes: bytes = b""
    prewrite_read_bytes: bytes = b""
    response_bytes: bytes = b'{"T":1051,"x":0,"y":0,"z":0}\n'
    fail_operations: tuple[str, ...] = ()
    pending_kind: str = "none"
    pending_outcome: str = "complete"
    cancel_outcome: str = "aborted"
    short_write: int | None = None
    read_fragment_bytes: int = 1024
    state_mismatch: bool = False
    timeout_mismatch: bool = False
    communication_error: int = 0
    invalid_completion: str = "none"

    def __post_init__(self) -> None:
        for value in (
            self.startup_bytes,
            self.prewrite_read_bytes,
            self.response_bytes,
        ):
            if type(value) is not bytes or len(value) > MAX_IO_BYTES:
                raise NativeSerialError("INVALID_FIXTURE", "fixture_bytes")
        operations = {
            "create_file",
            "create_event:1",
            "create_event:2",
            "get_state",
            "set_state",
            "get_timeouts",
            "set_timeouts",
            "queue_status",
            "submit_read",
            "submit_write",
            "complete_io",
            "cancel_io",
            "close_port",
            "close_event:1",
            "close_event:2",
        }
        if (
            type(self.fail_operations) is not tuple
            or len(self.fail_operations) > len(operations)
            or any(
                type(v) is not str or v not in operations for v in self.fail_operations
            )
        ):
            raise NativeSerialError("INVALID_FIXTURE", "fail_operations")
        for name, choices in (
            ("pending_kind", {"none", "read", "write"}),
            ("pending_outcome", {"complete", "timeout", "failed"}),
            (
                "cancel_outcome",
                {"aborted", "completed", "not_found_completed", "stuck"},
            ),
            ("invalid_completion", {"none", "bool_count", "overcount", "nonbytes"}),
        ):
            if (
                type(getattr(self, name)) is not str
                or getattr(self, name) not in choices
            ):
                raise NativeSerialError("INVALID_FIXTURE", name)
        for name in ("state_mismatch", "timeout_mismatch"):
            if type(getattr(self, name)) is not bool:
                raise NativeSerialError("INVALID_FIXTURE", name)
        if self.short_write is not None:
            _int(self.short_write, 0, len(FIXED_QUERY) - 1, "short_write")
        _int(self.read_fragment_bytes, 1, 1024, "read_fragment_bytes")
        _int(self.communication_error, 0, 0xFFFFFFFF, "communication_error")


class IncapableWin32SerialApi:
    """Sealed native-result fixture. Its integer handles are in-memory IDs."""

    __slots__ = (
        "_scenario",
        "_trace",
        "_handles",
        "_next",
        "_event_count",
        "_created",
        "_state",
        "_timeouts",
        "_state_set",
        "_timeouts_set",
        "_input",
        "_response_injected",
        "_prewrite_injected",
    )

    def __init__(
        self, scenario: IncapableWin32Scenario = IncapableWin32Scenario()
    ) -> None:
        if type(scenario) is not IncapableWin32Scenario:
            raise NativeSerialError("INVALID_FIXTURE", "scenario")
        self._scenario = scenario
        self._trace: list[tuple[str, tuple[Any, ...]]] = []
        self._handles: dict[int, str] = {}
        self._next = 101
        self._event_count = 0
        self._created = False
        self._state = DcbSettings(baud_rate=9600)
        self._timeouts = CommTimeouts(read_constant_ms=0)
        self._state_set = False
        self._timeouts_set = False
        self._input = bytearray(scenario.startup_bytes)
        self._response_injected = False
        self._prewrite_injected = False

    @property
    def trace(self) -> tuple[tuple[str, tuple[Any, ...]], ...]:
        return tuple(self._trace)

    @property
    def remaining_input(self) -> bytes:
        return bytes(self._input)

    @property
    def open_handles(self) -> tuple[int, ...]:
        return tuple(self._handles)

    def _call(self, operation: str, *values: Any) -> None:
        if len(self._trace) >= MAX_CALLS:
            raise NativeSerialError("FIXTURE_CALL_LIMIT", operation)
        self._trace.append((operation, values))
        if operation in self._scenario.fail_operations:
            raise NativeSerialError("WIN32_CALL_FAILED", operation, 5)

    def _new(self, kind: str) -> int:
        value = self._next
        self._next += 1
        self._handles[value] = kind
        return value

    def _port(self, handle: int) -> None:
        if self._handles.get(handle) != "port":
            raise NativeSerialError("INVALID_HANDLE", "fixture_port", 6)

    def create_file(self, path: str) -> int:
        _validate_com_path(path)
        self._call("create_file", path, 0xC0000000, 0, None, 3, 0x40000080, None)
        if self._created:
            raise NativeSerialError("ONE_USE_API", "create_file")
        self._created = True
        return self._new("port")

    def create_event(self) -> int:
        self._event_count += 1
        self._call(f"create_event:{self._event_count}", None, True, False, None)
        return self._new(f"event:{self._event_count}")

    def get_state(self, handle: int) -> DcbSettings:
        self._port(handle)
        self._call("get_state", handle)
        if self._state_set and self._scenario.state_mismatch:
            return replace(self._state, flags=0x1001)
        return self._state

    def set_state(self, handle: int, settings: DcbSettings) -> None:
        self._port(handle)
        self._call("set_state", handle, settings)
        self._state, self._state_set = settings, True

    def get_timeouts(self, handle: int) -> CommTimeouts:
        self._port(handle)
        self._call("get_timeouts", handle)
        if self._timeouts_set and self._scenario.timeout_mismatch:
            return replace(self._timeouts, read_constant_ms=0)
        return self._timeouts

    def set_timeouts(self, handle: int, settings: CommTimeouts) -> None:
        self._port(handle)
        self._call("set_timeouts", handle, settings)
        self._timeouts, self._timeouts_set = settings, True

    def queue_status(self, handle: int) -> QueueStatus:
        self._port(handle)
        self._call("queue_status", handle)
        return QueueStatus(
            len(self._input), error_mask=self._scenario.communication_error
        )

    def _done(self, token: IoToken) -> IoCompletion:
        if token.completion is not None:
            return token.completion
        if token.kind == "write":
            count = (
                len(token.payload)
                if self._scenario.short_write is None
                else self._scenario.short_write
            )
            result = IoCompletion("COMPLETE", count)
            if count == len(FIXED_QUERY) and not self._response_injected:
                self._input.extend(self._scenario.response_bytes)
                self._response_injected = True
        else:
            if not self._response_injected and not self._prewrite_injected:
                self._input.extend(self._scenario.prewrite_read_bytes)
                self._prewrite_injected = True
            count = min(
                token.size, self._scenario.read_fragment_bytes, len(self._input)
            )
            data = bytes(self._input[:count])
            del self._input[:count]
            result = IoCompletion("COMPLETE", count, data)
        fault = self._scenario.invalid_completion
        if fault == "bool_count":
            result = replace(result, transferred=False)
        elif fault == "overcount":
            result = replace(result, transferred=token.size + 1)
        elif fault == "nonbytes":
            result = replace(result, data="not bytes")  # type: ignore[arg-type]
        token.completion = result
        return result

    def submit_io(self, handle: int, token: IoToken) -> IoCompletion:
        validate_native_io_token(token)
        self._port(handle)
        self._call(f"submit_{token.kind}", handle, token.size)
        if token.submitted or token.event not in self._handles:
            raise NativeSerialError("INVALID_IO_TOKEN", "submit_io")
        token.submitted = True
        if token.kind == self._scenario.pending_kind:
            return IoCompletion("PENDING", winerror=997)
        return self._done(token)

    def complete_io(self, handle: int, token: IoToken, timeout_ms: int) -> IoCompletion:
        self._port(handle)
        self._call("complete_io", handle, timeout_ms)
        if token.cancelled:
            if self._scenario.cancel_outcome == "stuck":
                return IoCompletion("PENDING", winerror=258)
            if self._scenario.cancel_outcome == "aborted":
                return IoCompletion("ABORTED", winerror=995)
            return self._done(token)
        if self._scenario.pending_outcome == "timeout":
            return IoCompletion("PENDING", winerror=258)
        if self._scenario.pending_outcome == "failed":
            return IoCompletion("FAILED", winerror=31)
        return self._done(token)

    def cancel_io(self, handle: int, token: IoToken) -> str:
        self._port(handle)
        self._call("cancel_io", handle)
        token.cancelled = True
        return (
            "NOT_FOUND"
            if self._scenario.cancel_outcome == "not_found_completed"
            else "REQUESTED"
        )

    def close_handle(self, handle: int) -> None:
        kind = self._handles.get(handle)
        self._call(f"close_{kind}", handle)
        if kind is None:
            raise NativeSerialError("INVALID_HANDLE", "close_handle", 6)
        del self._handles[handle]


# Fixed-width types keep structure layout reviewable without loading kernel32.
_DWORD, _WORD, _BYTE = ctypes.c_uint32, ctypes.c_uint16, ctypes.c_ubyte
_HANDLE, _BOOL = ctypes.c_void_p, ctypes.c_int32


class _DCB(ctypes.Structure):
    _fields_ = [
        ("length", _DWORD),
        ("baud_rate", _DWORD),
        ("flags", _DWORD),
        ("reserved", _WORD),
        ("xon_limit", _WORD),
        ("xoff_limit", _WORD),
        ("byte_size", _BYTE),
        ("parity", _BYTE),
        ("stop_bits", _BYTE),
        ("xon_char", _BYTE),
        ("xoff_char", _BYTE),
        ("error_char", _BYTE),
        ("eof_char", _BYTE),
        ("event_char", _BYTE),
        ("reserved1", _WORD),
    ]


class _TIMEOUTS(ctypes.Structure):
    _fields_ = [(name, _DWORD) for name in CommTimeouts.__dataclass_fields__]


class _COMSTAT(ctypes.Structure):
    _fields_ = [("flags", _DWORD), ("input_bytes", _DWORD), ("output_bytes", _DWORD)]


class _OVERLAPPED(ctypes.Structure):
    _fields_ = [
        ("Internal", ctypes.c_size_t),
        ("InternalHigh", ctypes.c_size_t),
        ("Offset", _DWORD),
        ("OffsetHigh", _DWORD),
        ("hEvent", _HANDLE),
    ]


# The driver may still hold these buffers after cancellation or a caller fault.
# One outstanding native operation per helper process is the closed policy.
# Entries are removed ONLY following verified terminal completion.
_PINNED_NATIVE_IO: dict[int, tuple[Any, IoToken]] = {}


def _native_release_hold() -> None:
    raise NativeSerialError(NATIVE_HOLD, "native_api_load")


class WindowsNativeSerialApi:
    """Implemented Win32 calls behind an unconditional source-controlled hold.

    Construction/status do not construct native APIs. There is intentionally
    no boolean, callback, environment setting or alternate DLL-path override.
    The held ctypes branch has NOT been exercised against a serial driver.
    """

    __slots__ = ("_dll",)

    def __init__(self) -> None:
        self._dll: Any = None

    def status(self) -> dict[str, Any]:
        return {
            "native_api_loaded": False,
            "physical_hold": NATIVE_HOLD,
            "physical_authority": False,
        }

    def _kernel(self) -> Any:
        _native_release_hold()  # Must precede even DLL construction.
        return self._load_kernel()

    def _load_kernel(self) -> Any:
        """Internal loader shared with the separately admitted passive facade.

        Not an admission API. Ordinary call methods enter through held _kernel;
        the passive override supplies its own process-local one-use admission.
        """
        if os.name != "nt":
            raise NativeSerialError("WINDOWS_REQUIRED", "native_api_load")
        if self._dll is None:
            dll = ctypes.WinDLL("kernel32", use_last_error=True)
            signatures = {
                "CreateFileW": (
                    [
                        ctypes.c_wchar_p,
                        _DWORD,
                        _DWORD,
                        _HANDLE,
                        _DWORD,
                        _DWORD,
                        _HANDLE,
                    ],
                    _HANDLE,
                ),
                "CreateEventW": ([_HANDLE, _BOOL, _BOOL, ctypes.c_wchar_p], _HANDLE),
                "GetCommState": ([_HANDLE, ctypes.POINTER(_DCB)], _BOOL),
                "SetCommState": ([_HANDLE, ctypes.POINTER(_DCB)], _BOOL),
                "GetCommTimeouts": ([_HANDLE, ctypes.POINTER(_TIMEOUTS)], _BOOL),
                "SetCommTimeouts": ([_HANDLE, ctypes.POINTER(_TIMEOUTS)], _BOOL),
                "ClearCommError": (
                    [_HANDLE, ctypes.POINTER(_DWORD), ctypes.POINTER(_COMSTAT)],
                    _BOOL,
                ),
                "ReadFile": (
                    [
                        _HANDLE,
                        _HANDLE,
                        _DWORD,
                        ctypes.POINTER(_DWORD),
                        ctypes.POINTER(_OVERLAPPED),
                    ],
                    _BOOL,
                ),
                "WriteFile": (
                    [
                        _HANDLE,
                        _HANDLE,
                        _DWORD,
                        ctypes.POINTER(_DWORD),
                        ctypes.POINTER(_OVERLAPPED),
                    ],
                    _BOOL,
                ),
                "GetOverlappedResultEx": (
                    [
                        _HANDLE,
                        ctypes.POINTER(_OVERLAPPED),
                        ctypes.POINTER(_DWORD),
                        _DWORD,
                        _BOOL,
                    ],
                    _BOOL,
                ),
                "CancelIoEx": ([_HANDLE, ctypes.POINTER(_OVERLAPPED)], _BOOL),
                "CloseHandle": ([_HANDLE], _BOOL),
            }
            for name, (args, result) in signatures.items():
                method = getattr(dll, name)
                method.argtypes, method.restype = args, result
            self._dll = dll
        return self._dll

    @staticmethod
    def _checked(success: Any, operation: str) -> None:
        if not success:
            raise NativeSerialError(
                "WIN32_CALL_FAILED", operation, ctypes.get_last_error()
            )

    def create_file(self, path: str) -> int:
        # No sharing, inheritable security attributes, template, or fallback.
        _validate_com_path(path)
        handle = self._kernel().CreateFileW(
            path, 0xC0000000, 0, None, 3, 0x40000080, None
        )
        if handle in (None, 0, ctypes.c_void_p(-1).value):
            raise NativeSerialError(
                "WIN32_CALL_FAILED", "CreateFileW", ctypes.get_last_error()
            )
        return int(handle)

    def create_event(self) -> int:
        handle = self._kernel().CreateEventW(None, True, False, None)
        self._checked(handle, "CreateEventW")
        return int(handle)

    def get_state(self, handle: int) -> DcbSettings:
        value = _DCB()
        value.length = ctypes.sizeof(_DCB)
        self._checked(
            self._kernel().GetCommState(handle, ctypes.byref(value)), "GetCommState"
        )
        return DcbSettings(
            **{
                name: int(getattr(value, name))
                for name in DcbSettings.__dataclass_fields__
            }
        )

    def set_state(self, handle: int, settings: DcbSettings) -> None:
        if settings != DcbSettings():
            raise NativeSerialError("UNREVIEWED_SETTINGS", "SetCommState")
        value = _DCB()
        value.length = ctypes.sizeof(_DCB)
        for name in DcbSettings.__dataclass_fields__:
            setattr(value, name, getattr(settings, name))
        self._checked(
            self._kernel().SetCommState(handle, ctypes.byref(value)), "SetCommState"
        )

    def get_timeouts(self, handle: int) -> CommTimeouts:
        value = _TIMEOUTS()
        self._checked(
            self._kernel().GetCommTimeouts(handle, ctypes.byref(value)),
            "GetCommTimeouts",
        )
        return CommTimeouts(
            **{
                name: int(getattr(value, name))
                for name in CommTimeouts.__dataclass_fields__
            }
        )

    def set_timeouts(self, handle: int, settings: CommTimeouts) -> None:
        if settings != CommTimeouts():
            raise NativeSerialError("UNREVIEWED_SETTINGS", "SetCommTimeouts")
        value = _TIMEOUTS(
            *(getattr(settings, name) for name in CommTimeouts.__dataclass_fields__)
        )
        self._checked(
            self._kernel().SetCommTimeouts(handle, ctypes.byref(value)),
            "SetCommTimeouts",
        )

    def queue_status(self, handle: int) -> QueueStatus:
        errors, value = _DWORD(), _COMSTAT()
        self._checked(
            self._kernel().ClearCommError(
                handle, ctypes.byref(errors), ctypes.byref(value)
            ),
            "ClearCommError",
        )
        # This acknowledges error flags, NOT queued input. The owner retains
        # and latches every nonzero error; acknowledgement is never recovery.
        return QueueStatus(value.input_bytes, value.output_bytes, errors.value)

    def submit_io(self, handle: int, token: IoToken) -> IoCompletion:
        validate_native_io_token(token)
        dll = self._kernel()
        if token.submitted or _PINNED_NATIVE_IO:
            raise NativeSerialError("OUTSTANDING_IO_HELD", "submit_io")
        buffer = ctypes.create_string_buffer(token.size)
        if token.kind == "write":
            ctypes.memmove(buffer, token.payload, token.size)
        overlapped = _OVERLAPPED()
        overlapped.hEvent = token.event
        token.storage = (buffer, overlapped)
        token.submitted = True
        _PINNED_NATIVE_IO[id(token)] = (self, token)
        method = dll.ReadFile if token.kind == "read" else dll.WriteFile
        success = method(handle, buffer, token.size, None, ctypes.byref(overlapped))
        if success:
            return self.complete_io(handle, token, 0)
        error = ctypes.get_last_error()
        if error == 997:
            return IoCompletion("PENDING", winerror=error)
        _PINNED_NATIVE_IO.pop(id(token))
        return IoCompletion("ABORTED" if error == 995 else "FAILED", winerror=error)

    def complete_io(self, handle: int, token: IoToken, timeout_ms: int) -> IoCompletion:
        dll = self._kernel()
        _int(timeout_ms, 0, 1000, "completion_timeout_ms")
        buffer, overlapped = token.storage
        count = _DWORD()
        success = dll.GetOverlappedResultEx(
            handle, ctypes.byref(overlapped), ctypes.byref(count), timeout_ms, False
        )
        error = 0 if success else ctypes.get_last_error()
        if error in (996, 997, 258):
            return IoCompletion("PENDING", winerror=error)
        # Unexpected API failures need not prove the driver's operation is
        # terminal. Preserve the pin; the supervisor must resolve/terminate.
        if not success and error != 995:
            raise NativeSerialError(
                "COMPLETION_UNCONFIRMED", "GetOverlappedResultEx", error
            )
        _PINNED_NATIVE_IO.pop(id(token), None)
        if not success:
            return IoCompletion("ABORTED", winerror=error)
        if count.value > token.size:
            raise NativeSerialError("INVALID_COMPLETION_COUNT", "GetOverlappedResultEx")
        data = bytes(buffer.raw[: count.value]) if token.kind == "read" else b""
        return IoCompletion("COMPLETE", count.value, data)

    def cancel_io(self, handle: int, token: IoToken) -> str:
        dll = self._kernel()
        _, overlapped = token.storage
        success = dll.CancelIoEx(handle, ctypes.byref(overlapped))
        if success:
            return "REQUESTED"
        error = ctypes.get_last_error()
        if error == 1168:
            return "NOT_FOUND"  # Still requires independent completion check.
        raise NativeSerialError("WIN32_CALL_FAILED", "CancelIoEx", error)

    def close_handle(self, handle: int) -> None:
        self._checked(self._kernel().CloseHandle(handle), "CloseHandle")
