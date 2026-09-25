"""Exclusive handle owner for the separately admitted endpoint native facade.

No discovery, purge, reset, implicit feedback query, fallback or reopen exists.
The parent worker must enforce wall-clock termination for a stuck native call.
This owner provides bounded ordinary waits and preserves uncertain cleanup.
"""

import base64
from threading import RLock
import time

from rocell.application.endpoint_trial_contract import EndpointTrialRequest
from rocell.application.endpoint_owned_trial import EndpointCleanupResult
from rocell.arm.protocol import encode_line
from .endpoint_serial_api import WindowsEndpointSerialApi
from .nonpurging_serial_api import DcbSettings, CommTimeouts, QueueStatus, IoToken, IoCompletion, NativeSerialError, _int


class EndpointSerialConnection:
    def __init__(self, request, api, *, clock_ns=time.monotonic_ns):
        if (type(request) is not EndpointTrialRequest or type(api) is not WindowsEndpointSerialApi
                or api.admitted_request_sha256 != request.request_sha256 or not callable(clock_ns)):
            raise ValueError('Exact admitted endpoint facade/request required')
        self._initialize_owned_state(request, api, clock_ns)

    def _initialize_owned_state(self, request, api, clock_ns):
        """Shared handle lifecycle state, called only after typed admission."""
        self._request, self._api, self._clock = request, api, clock_ns
        self._lock = RLock()
        self._phase = 'UNOPENED'
        self._port = None
        self._events, self._owned = {}, []
        self._pending = None
        self._open_attempted = self._write_attempted = self._close_attempted = False
        self._read_calls = {'baseline':0,'post':0}
        self._read_bytes = {'baseline':0,'post':0}
        self._write_bytes = 0
        self._late_read = b''
        self._errors = []
        self._last_ns = 0

    def _now(self):
        value = self._clock()
        if type(value) is not int or not 0 < value < 2**63 or value < self._last_ns:
            raise ValueError('Invalid endpoint lifecycle clock')
        self._last_ns = value
        return value

    def _error(self, error, stage):
        if len(self._errors)<16:
            self._errors.append({'stage':stage, 'code':error.code if type(error) is NativeSerialError else type(error).__name__})

    def _queue(self):
        value = self._api.queue_status(self._port)
        if (type(value) is not QueueStatus
                or any(type(v) is not int or not 0 <= v <= 0xffffffff
                       for v in (value.input_bytes,value.output_bytes,value.error_mask))
                or value.error_mask or value.output_bytes):
            raise NativeSerialError('ENDPOINT_COMM_STATE_UNSAFE','queue_status')
        return value

    def open(self):
        with self._lock:
            if self._open_attempted or self._close_attempted:
                raise ValueError('Endpoint connection cannot reopen')
            self._open_attempted = True
            self._phase = 'OPENING'
            try:
                started = self._now()
                self._request.require_start_time(started)
                self._port = self._api.create_file(self._api.expected_path)
                self._owned.append(self._port)
                self._queue()  # Input is allowed and will be retained, never purged.
                for kind in ('read','write'):
                    handle = self._api.create_event()
                    self._owned.append(handle)
                    self._events[kind] = handle
                if type(self._api.get_state(self._port)) is not DcbSettings:
                    raise ValueError('Invalid DCB readback')
                self._api.set_state(self._port,DcbSettings())
                if self._api.get_state(self._port) != DcbSettings():
                    raise ValueError('DCB settings mismatch')
                if type(self._api.get_timeouts(self._port)) is not CommTimeouts:
                    raise ValueError('Invalid timeout readback')
                self._api.set_timeouts(self._port,CommTimeouts())
                if self._api.get_timeouts(self._port) != CommTimeouts():
                    raise ValueError('Timeout settings mismatch')
                self._queue()
                if self._now()-started > 2_000_000_000:
                    raise ValueError('Open setup exceeded two-second budget')
                self._phase = 'OPEN'
            except Exception as error:
                self._error(error,'open')
                self._phase = 'FAILED'
                self.close(2000)
                raise

    def _completion(self, token, result):
        if (type(result) is not IoCompletion or result.state not in {'COMPLETE','PENDING','ABORTED','FAILED'}
                or type(result.transferred) is not int or not 0 <= result.transferred <= token.size
                or type(result.winerror) is not int or not 0 <= result.winerror <= 0xffffffff
                or type(result.data) is not bytes):
            raise ValueError('Invalid native completion')
        if result.state == 'COMPLETE':
            if result.winerror or len(result.data) != (result.transferred if token.kind=='read' else 0):
                raise ValueError('Inconsistent completed I/O')
        elif result.transferred or result.data or not result.winerror:
            raise ValueError('Inconsistent pending/error I/O')
        if result.state != 'PENDING':
            self._pending = None
        return result

    def _io(self, kind, size, payload, timeout_ms):
        if self._phase != 'OPEN' or self._pending is not None:
            raise ValueError('Open idle endpoint connection required')
        token = IoToken(self._events[kind],kind,size,payload)
        self._pending = token
        try:
            result = self._completion(token,self._api.submit_io(self._port,token))
            if result.state == 'PENDING':
                result = self._completion(token,self._api.complete_io(self._port,token,timeout_ms))
            if result.state != 'COMPLETE':
                raise NativeSerialError('ENDPOINT_IO_NOT_COMPLETED',kind,result.winerror)
            return result
        except Exception as error:
            if token.submitted is False and token.storage is None:
                # The exact facade refused before native submission. There is
                # no driver-owned buffer to cancel; still do not retry the I/O.
                self._pending = None
            self._error(error,kind)
            self._phase = 'FAILED'
            raise

    def read(self, maximum_bytes, timeout_ms):
        with self._lock:
            if self._phase != 'OPEN' or self._pending is not None:
                raise ValueError('Open idle endpoint connection required')
            _int(maximum_bytes,1,256,'read_size')
            _int(timeout_ms,1,100,'read_timeout')
            phase = 'post' if self._write_attempted else 'baseline'
            limits = self._runtime_body()['limits']
            if (self._read_calls[phase] >= limits[f'maximum_{phase}_reads']
                    or self._read_bytes[phase]+maximum_bytes > limits[f'maximum_{phase}_bytes']):
                raise ValueError('Endpoint read budget exhausted')
            self._read_calls[phase] += 1
            available = self._queue().input_bytes
            if not available:
                # Do not submit a 256-byte read against an empty queue: the
                # reviewed driver timeout is longer than a capture poll. The
                # collector supplies the cancellable idle wait and total budget.
                return b''
            result = self._io('read',min(maximum_bytes,available),b'',timeout_ms)
            self._read_bytes[phase] += result.transferred
            return result.data

    def _runtime_body(self):
        return self._request.to_dict()

    def _motion_payload(self):
        return encode_line(self._request.goal().to_message())

    def write_once(self, payload):
        with self._lock:
            if self._write_attempted:
                raise ValueError('One endpoint write; no retry')
            self._write_attempted = True
            if self._phase != 'OPEN' or self._pending is not None:
                raise ValueError('Open idle endpoint connection required')
            if type(payload) is not bytes or payload != self._motion_payload():
                raise ValueError('Exact endpoint payload required')
            self._queue()
            result = self._io('write',len(payload),payload,1000)
            self._write_bytes = result.transferred
            return result.transferred

    def close(self, timeout_ms):
        with self._lock:
            _int(timeout_ms,1,2000,'cleanup_timeout')
            if self._close_attempted:
                return EndpointCleanupResult(not self._owned, int(self._pending is not None))
            self._close_attempted = True
            # Even clock failure must not skip the first cleanup attempt.
            try:
                deadline = self._now()+timeout_ms*1_000_000
            except Exception as error:
                deadline = None
                self._error(error,'cleanup_clock')
            token = self._pending
            if token is not None:
                try:
                    self._api.cancel_io(self._port,token)
                except Exception as error:
                    self._error(error,'cancel')
                try:
                    result = self._completion(token,self._api.complete_io(self._port,token,min(250,timeout_ms)))
                    if result.state == 'COMPLETE':
                        if token.kind == 'read': self._late_read = result.data
                        else: self._write_bytes = result.transferred
                except Exception as error:
                    self._error(error,'cancel_completion')
            if self._pending is None:
                for handle in reversed(tuple(self._owned)):
                    try:
                        if deadline is not None and self._now() >= deadline:
                            raise ValueError('Cleanup deadline expired')
                        self._api.close_handle(handle)
                        self._owned.remove(handle)
                    except Exception as error:
                        self._error(error,'close_handle')
            clean = not self._owned and self._pending is None
            self._phase = 'CLOSED' if clean else 'CLEANUP_UNCONFIRMED'
            return EndpointCleanupResult(clean,int(self._pending is not None))

    def snapshot(self):
        with self._lock:
            return {'schema':'rocell.endpoint_connection_lifecycle.v1','phase':self._phase,
                'request_sha256':self._request.request_sha256,'connection_id':self._api.connection_id,
                'owned_handle_count':len(self._owned),'pending_io_count':int(self._pending is not None),
                'read_calls':dict(self._read_calls),'read_bytes':dict(self._read_bytes),
                'confirmed_write_bytes':self._write_bytes,
                'late_cleanup_read_base64':base64.b64encode(self._late_read).decode('ascii'),
                'errors':[dict(item) for item in self._errors], 'physical_stop_verified':False}
