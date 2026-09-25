"""Handle-owner tests with fake Win32 calls; no actual DLL or device access."""

import base64
import ctypes
from dataclasses import replace

import pytest

from rocell.arm.protocol import encode_line
from rocell.safety.bench_endpoint import authorize_bench_endpoint
from rocell.providers.windows.endpoint_serial_api import WindowsEndpointSerialApi
from rocell.providers.windows.endpoint_serial_connection import EndpointSerialConnection
from rocell.providers.windows.nonpurging_serial_api import (
    WindowsNativeSerialApi, DcbSettings, CommTimeouts, _PINNED_NATIVE_IO,
)
from test_bench_review_authority import fixture
from test_endpoint_serial_api import FakeKernel


class OwnerKernel(FakeKernel):
    def __init__(self):
        super().__init__()
        self.closed = []
        self.bad_settings = False
        self.fail_setup = False
        self.completion_ready = True
        self.cancel_completes = True
        self.last_error = 997
        self.cancel_calls = 0
        self.input = b'baseline\n'
    def GetCommState(self, handle, value):
        for name in DcbSettings.__dataclass_fields__:
            setattr(value._obj,name,getattr(DcbSettings(),name))
        if self.bad_settings: value._obj.baud_rate = 9600
        return True
    def SetCommState(self, handle, value):
        if self.fail_setup: raise RuntimeError('private failure')
        return True
    def GetCommTimeouts(self, handle, value):
        for name in CommTimeouts.__dataclass_fields__:
            setattr(value._obj,name,getattr(CommTimeouts(),name))
        return True
    def SetCommTimeouts(self,*args): return True
    def ClearCommError(self,handle,error,value):
        error._obj.value = 0
        value._obj.input_bytes = len(self.input)
        value._obj.output_bytes = 0
        return True
    def ReadFile(self,handle,buffer,size,count,overlapped):
        data = self.input[:size]
        ctypes.memmove(buffer,data,len(data))
        self.size = len(data)
        return not self.pending
    def GetOverlappedResultEx(self,*args):
        if not self.completion_ready:
            self.last_error = 997
            return False
        return super().GetOverlappedResultEx(*args)
    def CancelIoEx(self,*args):
        self.cancel_calls += 1
        self.completion_ready = self.cancel_completes
        self.last_error = 1168  # Cancellation NOT_FOUND still needs completion.
        return False
    def CloseHandle(self,handle):
        self.closed.append(handle)
        return True


def owner(tmp_path,monkeypatch):
    req, authority, records, raw, filename, reader, tick, current = fixture(tmp_path)
    current[0] = replace(current[0],port_name='COM7')
    permit = authorize_bench_endpoint(req,connection_id='owned-test',evidence_reader=reader,
                                     attempt_root=tmp_path,clock=lambda:tick[0])
    kernel = OwnerKernel()
    def load(api):
        api._dll = kernel
        return kernel
    monkeypatch.setattr(WindowsNativeSerialApi,'_load_kernel',load)
    monkeypatch.setattr(ctypes,'get_last_error',lambda:kernel.last_error,raising=False)
    api = WindowsEndpointSerialApi.from_bench_permit(req,permit,port_name='COM7',connection_id='owned-test')
    connection = EndpointSerialConnection(req,api,clock_ns=lambda:tick[0])
    return req,permit,connection,kernel


def test_open_read_exact_write_and_reverse_handle_cleanup(tmp_path,monkeypatch):
    req,permit,connection,kernel = owner(tmp_path,monkeypatch)
    connection.open()
    assert connection.read(256,100) == kernel.input
    assert permit.consume(req,'owned-test',baseline_acquired_ns=1_000_000_000)
    payload = encode_line(req.goal().to_message())
    assert connection.write_once(payload) == len(payload)
    assert connection.read(256,100) == kernel.input
    assert connection.close(2000).all_handles_closed
    assert kernel.closed == [202,201,101]
    result = connection.snapshot()
    assert result['read_bytes'] == {'baseline':len(kernel.input),'post':len(kernel.input)}
    assert result['confirmed_write_bytes'] == len(payload)
    with pytest.raises(ValueError): connection.open()
    with pytest.raises(ValueError): connection.write_once(payload)
    assert connection.close(2000).all_handles_closed and len(kernel.closed)==3


@pytest.mark.parametrize('fault',['bad_settings','fail_setup'])
def test_setup_failure_closes_all_acquired_handles_without_write(tmp_path,monkeypatch,fault):
    req,permit,connection,kernel = owner(tmp_path,monkeypatch)
    setattr(kernel,fault,True)
    with pytest.raises(Exception): connection.open()
    assert kernel.closed == [202,201,101] and kernel.writes == []
    assert connection.snapshot()['owned_handle_count'] == 0
    assert 'private' not in str(connection.snapshot())


def test_timeout_then_late_completion_retains_bytes_and_closes(tmp_path,monkeypatch):
    req,permit,connection,kernel = owner(tmp_path,monkeypatch)
    connection.open()
    kernel.pending = True
    kernel.completion_ready = False
    with pytest.raises(Exception): connection.read(256,100)
    assert connection.snapshot()['pending_io_count'] == 1
    assert connection.close(2000).all_handles_closed
    assert kernel.cancel_calls == 1
    assert base64.b64decode(connection.snapshot()['late_cleanup_read_base64']) == kernel.input
    assert kernel.closed == [202,201,101]


def test_unresolved_cancellation_keeps_native_resources_alive(tmp_path,monkeypatch):
    req,permit,connection,kernel = owner(tmp_path,monkeypatch)
    connection.open()
    kernel.pending = True
    kernel.completion_ready = kernel.cancel_completes = False
    try:
        with pytest.raises(Exception): connection.read(256,100)
        token = connection._pending
        cleanup = connection.close(2000)
        assert not cleanup.all_handles_closed and cleanup.pending_io_count == 1
        assert kernel.closed == [] and id(token) in _PINNED_NATIVE_IO
        connection.close(2000)
        assert kernel.cancel_calls == 1
    finally:
        # Only release this test's fake token after assertions, never other pins.
        if connection._pending is not None:
            _PINNED_NATIVE_IO.pop(id(connection._pending),None)


def test_no_read_before_open_or_after_close(tmp_path,monkeypatch):
    req,permit,connection,kernel = owner(tmp_path,monkeypatch)
    with pytest.raises(ValueError): connection.read(256,100)
    connection.close(2000)
    with pytest.raises(ValueError): connection.read(256,100)
    assert kernel.closed == [] and kernel.writes == []


def test_empty_queue_does_not_submit_a_driver_read(tmp_path,monkeypatch):
    req,permit,connection,kernel = owner(tmp_path,monkeypatch)
    connection.open()
    kernel.input = b''
    kernel.ReadFile = lambda *_:pytest.fail('Empty queue must not submit a read')
    assert connection.read(256,100) == b''
    assert connection.snapshot()['pending_io_count'] == 0
    assert connection.close(2000).all_handles_closed
