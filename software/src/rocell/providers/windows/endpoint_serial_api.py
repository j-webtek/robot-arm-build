"""Separate exact-endpoint Win32 facade, not registered for wizard live access.

The existing fixed-query and zero-write facades are unchanged. This facade
requires authenticated bench reviews for one open and a consumed, one-use
bench permit for one exact motion submission. A worker must still own handles,
bound wait/cancel/cleanup, enforce its source/runtime claim and retain evidence.
"""

import ctypes
from threading import Lock

from rocell.application.endpoint_trial_contract import EndpointTrialRequest
from rocell.arm.protocol import encode_line
from rocell.safety.bench_endpoint import BenchEndpointPermit
from .nonpurging_serial_api import (
    WindowsNativeSerialApi, NativeSerialError, IoToken, IoCompletion, _OVERLAPPED,
    _PINNED_NATIVE_IO, _validate_com_path, _int, validate_native_io_token,
    validate_owned_pending_io,
)


class WindowsEndpointSerialApi(WindowsNativeSerialApi):
    """Inert on construction; there is no arbitrary JSON or retry method."""

    def __init__(self, port_name):
        if type(port_name) is not str:
            raise ValueError('Exact COM endpoint required')
        self._path = '\\\\.\\'+port_name
        _validate_com_path(self._path)
        super().__init__()
        self._port_name = port_name
        self._request = self._permit = self._connection_id = None
        self._open_attempted = self._write_attempted = False
        self._open_lock, self._write_lock = Lock(), Lock()
        self._write_token = self._write_shape = self._write_storage = None
        self._port_handle = None
        self._event_handles = set()

    @classmethod
    def from_bench_permit(cls, request, permit, *, port_name, connection_id):
        if (cls is not WindowsEndpointSerialApi or type(request) is not EndpointTrialRequest
                or type(permit) is not BenchEndpointPermit):
            raise ValueError('Exact bench native composition required')
        instance = cls(port_name)
        permit.claim_native_open(request, connection_id, port_name)
        instance._request, instance._permit, instance._connection_id = request, permit, connection_id
        return instance

    def _kernel(self):
        if self._request is None:
            return super()._kernel()  # Default native hold; no DLL load.
        if self._dll is None:
            self._permit.validate_native_open(self._request, self._connection_id, self._port_name)
        # Once owned resources may exist, cleanup must remain available even
        # after review expiry. No deadline is interpreted as a physical stop.
        return self._load_kernel()

    @property
    def expected_path(self):
        return self._path

    @property
    def admitted_request_sha256(self):
        return None if self._request is None else self._request.request_sha256

    @property
    def connection_id(self):
        return self._connection_id

    def matches_authorization(self, request, permit):
        return self._request is request and self._permit is permit

    def _motion_payload(self):
        """Fixed payload for this facade's exact, already-admitted request type."""
        return encode_line(self._request.goal().to_message())

    def create_file(self, path):
        with self._open_lock:
            if self._open_attempted:
                raise NativeSerialError('ONE_BENCH_OPEN_NO_RETRY', 'create_file')
            self._open_attempted = True
            if path != self._path:
                raise NativeSerialError('BENCH_ENDPOINT_CHANGED', 'create_file')
            self._port_handle = super().create_file(path)
            return self._port_handle

    def submit_io(self, handle, token):
        self._require_handle(handle)
        if type(token) is not IoToken:
            raise NativeSerialError('INVALID_IO_TOKEN','submit_io')
        if token.event not in self._event_handles:
            raise NativeSerialError('UNOWNED_ENDPOINT_EVENT','submit_io')
        if token.kind == 'read':
            validate_native_io_token(token)
            _int(token.size, 1, 256, 'endpoint_read_size')
            return super().submit_io(handle, token)
        with self._write_lock:
            if self._write_attempted:
                raise NativeSerialError('ONE_ENDPOINT_WRITE_NO_RETRY','submit_io')
            self._write_attempted = True
            if self._request is None or not self._open_attempted:
                raise NativeSerialError('BENCH_NATIVE_NOT_ADMITTED','submit_io')
            payload = self._motion_payload()
            _int(token.event, 1, (1 << (ctypes.sizeof(ctypes.c_void_p)*8))-2, 'io_event')
            if (token.kind != 'write' or type(token.size) is not int or token.size != len(payload)
                    or type(token.payload) is not bytes or token.payload != payload
                    or token.submitted is not False or token.cancelled is not False
                    or token.storage is not None or token.completion is not None):
                raise NativeSerialError('EXACT_FRESH_ENDPOINT_WRITE_REQUIRED','submit_io')
            if _PINNED_NATIVE_IO:
                raise NativeSerialError('OUTSTANDING_IO_HELD','submit_io')
            self._permit.claim_native_dispatch(self._request, self._connection_id, self._port_name)
            dll = self._kernel()
            buffer = ctypes.create_string_buffer(token.size)
            ctypes.memmove(buffer, payload, token.size)
            overlapped = _OVERLAPPED()
            overlapped.hEvent = token.event
            token.storage = self._write_storage = (buffer, overlapped)
            token.submitted = True
            self._write_token = token
            self._write_shape = (token.event, token.kind, token.size, token.payload)
            _PINNED_NATIVE_IO[id(token)] = (self, token)
            # Exceptions leave the pin intact: do not free an uncertain buffer
            # or retry when the syscall's submission state is unknown.
            if dll.WriteFile(handle, buffer, token.size, None, ctypes.byref(overlapped)):
                return self.complete_io(handle, token, 0)
            error = ctypes.get_last_error()
            if error == 997:
                return IoCompletion('PENDING', winerror=error)
            _PINNED_NATIVE_IO.pop(id(token))
            return IoCompletion('ABORTED' if error == 995 else 'FAILED', winerror=error)

    def _owned(self, token):
        if type(token) is not IoToken:
            raise NativeSerialError('INVALID_IO_TOKEN','completion')
        if token.kind == 'read':
            validate_owned_pending_io(self, token)
            return
        pin = _PINNED_NATIVE_IO.get(id(token))
        if (token is not self._write_token or pin is None or pin[0] is not self or pin[1] is not token
                or token.storage is not self._write_storage
                or (token.event,token.kind,token.size,token.payload) != self._write_shape):
            raise NativeSerialError('UNOWNED_OR_CHANGED_ENDPOINT_IO','completion')

    def complete_io(self, handle, token, timeout_ms):
        self._require_handle(handle)
        self._owned(token)
        return super().complete_io(handle, token, timeout_ms)

    def cancel_io(self, handle, token):
        self._require_handle(handle)
        self._owned(token)
        return super().cancel_io(handle, token)

    def _require_handle(self, handle):
        if type(handle) is not int or self._port_handle is None or handle != self._port_handle:
            raise NativeSerialError('UNOWNED_ENDPOINT_HANDLE','io_admission')

    def create_event(self):
        if self._port_handle is None:
            raise NativeSerialError('ENDPOINT_NOT_OPEN','create_event')
        if len(self._event_handles) >= 2:
            raise NativeSerialError('ENDPOINT_EVENT_BUDGET','create_event')
        handle = super().create_event()
        self._event_handles.add(handle)
        return handle

    def close_handle(self, handle):
        if any(owner is self for owner, _ in _PINNED_NATIVE_IO.values()):
            raise NativeSerialError('PENDING_ENDPOINT_IO_RESOURCES_RETAINED','close_handle')
        if type(handle) is not int or (handle != self._port_handle and handle not in self._event_handles):
            raise NativeSerialError('UNOWNED_ENDPOINT_HANDLE','close_handle')
        if handle == self._port_handle:
            self._port_handle = None
        self._event_handles.discard(handle)
        return super().close_handle(handle)
