"""Dormant campaign-specific Win32 facade; no launcher or wizard registration.

Retains existing owned-handle and read/cleanup implementation. Writes have a
separate per-leg boundary; single-trial write guards are never reset. Native
process packaging, owned connection lifecycle and physical qualification remain
required before releasing this facade through an executable application path.
"""
import ctypes
import time
from threading import Event

from rocell.application.positional_campaign_launch import CampaignWorkerClaim
from rocell.safety.positional_campaign_admission import PositionalCampaignAdmission
from rocell.safety.positional_campaign_authority import PositionalCampaignIntent, BASE_SEQUENCE_SCHEMA
from .endpoint_serial_api import WindowsEndpointSerialApi
from .nonpurging_serial_api import (
    WindowsNativeSerialApi, NativeSerialError, IoToken, IoCompletion, _OVERLAPPED,
    _PINNED_NATIVE_IO, _int,
)


class WindowsPositionalCampaignSerialApi(WindowsEndpointSerialApi):
    def __init__(self, port_name):
        super().__init__(port_name)
        self._campaign_held = False
        self._campaign_tokens = []
        self._clock_ns = time.monotonic_ns
        self._cancellation = None

    @classmethod
    def from_campaign_claim(cls, request, admission, claim, *, port_name, connection_id, cancellation,
            clock_ns=time.monotonic_ns):
        if (cls is not WindowsPositionalCampaignSerialApi
                or type(request) is not PositionalCampaignIntent
                or type(admission) is not PositionalCampaignAdmission
                or type(claim) is not CampaignWorkerClaim
                or admission.request != request or claim._reader.request != request
                or connection_id != request.to_dict()['campaign_id'] or not callable(clock_ns)
                or type(cancellation) is not Event or cancellation.is_set()):
            raise ValueError('Exact process-claimed campaign composition required')
        instance = cls(port_name)
        claim.consume()
        admission.claim_open()
        admission.validate_connection_open(connection_id, port_name)
        instance._request, instance._permit, instance._connection_id = request, admission, connection_id
        instance._clock_ns = clock_ns
        instance._cancellation = cancellation
        return instance

    def _kernel(self):
        if self._request is None:
            return WindowsNativeSerialApi._kernel(self)
        if self._dll is None:
            if self._cancellation.is_set():
                raise NativeSerialError('CAMPAIGN_CANCELLED', 'open')
            self._permit.validate_connection_open(self._connection_id, self._port_name)
        # Once a handle can exist, cleanup must remain available after expiry.
        return self._load_kernel()

    def _motion_payload(self):
        return self._permit.selected_payload()

    def submit_io(self, handle, token):
        if type(token) is IoToken and token.kind == 'read':
            return super().submit_io(handle, token)
        with self._write_lock:
            if self._campaign_held:
                raise NativeSerialError('CAMPAIGN_SUBMISSION_HELD', 'submit_io')
            self._campaign_held = True
            try:
                self._require_handle(handle)
                if (type(token) is not IoToken or self._request is None or not self._open_attempted
                        or token.event not in self._event_handles or len(self._campaign_tokens) >= self._request.to_dict()['limits']['maximum_writes']
                        or any(previous is token for previous in self._campaign_tokens)):
                    raise NativeSerialError('EXACT_CAMPAIGN_IO_REQUIRED', 'submit_io')
                payload = self._motion_payload()
                _int(token.event, 1, (1 << (ctypes.sizeof(ctypes.c_void_p)*8))-2, 'io_event')
                if (token.kind != 'write' or type(token.size) is not int or token.size != len(payload)
                        or type(token.payload) is not bytes or token.payload != payload
                        or token.submitted is not False or token.cancelled is not False
                        or token.storage is not None or token.completion is not None):
                    raise NativeSerialError('EXACT_FRESH_CAMPAIGN_WRITE_REQUIRED', 'submit_io')
                if _PINNED_NATIVE_IO:
                    raise NativeSerialError('OUTSTANDING_IO_HELD', 'submit_io')
                # Allocate before final admission so allocation time cannot make
                # the baseline older after the last timestamp check.
                dll = self._kernel()
                buffer = ctypes.create_string_buffer(token.size)
                ctypes.memmove(buffer, payload, token.size)
                overlapped = _OVERLAPPED()
                overlapped.hEvent = token.event
                if self._cancellation.is_set():
                    raise NativeSerialError('CAMPAIGN_CANCELLED', 'submit_io')
                self._permit.claim_submission(payload, self._clock_ns())
                if self._cancellation.is_set():
                    raise NativeSerialError('CAMPAIGN_CANCELLED', 'submit_io')
                token.storage = self._write_storage = (buffer, overlapped)
                token.submitted = True
                self._campaign_tokens.append(token)
                self._write_token = token
                self._write_shape = (token.event, token.kind, token.size, token.payload)
                _PINNED_NATIVE_IO[id(token)] = (self, token)
                if dll.WriteFile(handle, buffer, token.size, None, ctypes.byref(overlapped)):
                    result = self.complete_io(handle, token, 0)
                else:
                    error = ctypes.get_last_error()
                    if error == 997:
                        result = IoCompletion('PENDING', winerror=error)
                    else:
                        _PINNED_NATIVE_IO.pop(id(token))
                        result = IoCompletion('ABORTED' if error == 995 else 'FAILED', winerror=error)
                self._campaign_held = not (result.state == 'PENDING'
                    or (result.state == 'COMPLETE' and result.transferred == token.size))
                if self._campaign_held:
                    self._permit.revoke()
                return result
            except Exception:
                # Never unpin or retry uncertain native submission; inherited
                # owned completion/cancel/close methods retain cleanup access.
                if self._permit is not None:
                    self._permit.revoke()
                raise

    def complete_io(self, handle, token, timeout_ms):
        try:
            result = super().complete_io(handle, token, timeout_ms)
        except Exception:
            if type(token) is IoToken and token.kind == 'write':
                self._campaign_held = True
                if self._permit is not None:
                    self._permit.revoke()
            raise
        if token.kind == 'write' and result.state != 'PENDING' and (
                result.state != 'COMPLETE' or result.transferred != token.size):
            self._campaign_held = True
            self._permit.revoke()
        return result
