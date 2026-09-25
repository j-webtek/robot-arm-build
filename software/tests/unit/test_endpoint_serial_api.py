"""Exercise native-facade boundaries through a fake kernel, never a Windows DLL."""

from dataclasses import replace
import ctypes

import pytest

from rocell.providers.windows.endpoint_serial_api import WindowsEndpointSerialApi
from rocell.providers.windows.nonpurging_serial_api import (
    WindowsNativeSerialApi, IoToken, NativeSerialError, validate_native_io_token,
    _PINNED_NATIVE_IO,
)
from rocell.arm.protocol import encode_line
from rocell.safety.bench_endpoint import authorize_bench_endpoint
from test_bench_review_authority import fixture


class FakeKernel:
    def __init__(self):
        self.writes = []
        self.events = 200
        self.pending = False

    def CreateFileW(self, *args): return 101
    def CreateEventW(self, *args):
        self.events += 1
        return self.events
    def WriteFile(self, handle, buffer, size, count, overlapped):
        self.writes.append(bytes(buffer.raw[:size]))
        self.size = size
        return not self.pending
    def GetOverlappedResultEx(self, handle, overlapped, count, timeout, alertable):
        count._obj.value = self.size
        return True
    def CloseHandle(self, handle): return True


def admitted(tmp_path, monkeypatch):
    req, authority, records, raw, filename, reader, tick, current = fixture(tmp_path)
    current[0] = replace(current[0], port_name='COM7')
    permit = authorize_bench_endpoint(req, connection_id='owned-test', evidence_reader=reader,
                                     attempt_root=tmp_path, clock=lambda:tick[0])
    kernel = FakeKernel()
    def load(api):
        api._dll = kernel
        return kernel
    monkeypatch.setattr(WindowsNativeSerialApi, '_load_kernel', load)
    api = WindowsEndpointSerialApi.from_bench_permit(req, permit, port_name='COM7', connection_id='owned-test')
    handle = api.create_file('\\\\.\\COM7')
    event = api.create_event()
    payload = encode_line(req.goal().to_message())
    return req, permit, api, handle, IoToken(event,'write',len(payload),payload), kernel, current


def test_exact_consumed_endpoint_write_completes_and_is_not_repeatable(tmp_path, monkeypatch):
    req, permit, api, handle, token, kernel, _ = admitted(tmp_path, monkeypatch)
    assert permit.consume(req,'owned-test',baseline_acquired_ns=1_000_000_000)
    result = api.submit_io(handle, token)
    assert result.state == 'COMPLETE' and result.transferred == token.size
    assert kernel.writes == [token.payload] and id(token) not in _PINNED_NATIVE_IO
    with pytest.raises(NativeSerialError): api.submit_io(handle, token)
    api.close_handle(handle)
    with pytest.raises(NativeSerialError): api.submit_io(handle, token)


def test_unconsumed_permit_cannot_write_and_attempt_is_burned(tmp_path, monkeypatch):
    req, permit, api, handle, token, kernel, _ = admitted(tmp_path, monkeypatch)
    with pytest.raises(ValueError): api.submit_io(handle, token)
    assert permit.consume(req,'owned-test',baseline_acquired_ns=1_000_000_000)
    with pytest.raises(NativeSerialError): api.submit_io(handle, token)
    assert kernel.writes == []


@pytest.mark.parametrize('payload',[b'{"T":105}\n',b'{"T":999}\n',b'{"T":0}\n',b'{"T":1041}\n'])
def test_other_commands_are_not_admitted(tmp_path,monkeypatch,payload):
    req, permit, api, handle, token, kernel, _ = admitted(tmp_path,monkeypatch)
    assert permit.consume(req,'owned-test',baseline_acquired_ns=1_000_000_000)
    token.payload, token.size = payload, len(payload)
    with pytest.raises(NativeSerialError): api.submit_io(handle,token)
    assert kernel.writes == []


def test_original_feedback_validator_still_rejects_motion(tmp_path,monkeypatch):
    req, permit, api, handle, token, kernel, _ = admitted(tmp_path,monkeypatch)
    with pytest.raises(NativeSerialError): validate_native_io_token(token)
    assert kernel.writes == []


def test_changed_port_context_blocks_native_dispatch(tmp_path,monkeypatch):
    req, permit, api, handle, token, kernel, current = admitted(tmp_path,monkeypatch)
    assert permit.consume(req,'owned-test',baseline_acquired_ns=1_000_000_000)
    current[0] = replace(current[0],port_name='COM9')
    with pytest.raises(ValueError): api.submit_io(handle,token)
    assert kernel.writes == []


def test_pending_buffer_is_pinned_until_terminal_completion(tmp_path,monkeypatch):
    req, permit, api, handle, token, kernel, _ = admitted(tmp_path,monkeypatch)
    assert permit.consume(req,'owned-test',baseline_acquired_ns=1_000_000_000)
    kernel.pending = True
    monkeypatch.setattr(ctypes,'get_last_error',lambda:997,raising=False)
    try:
        result = api.submit_io(handle,token)
        assert result.state == 'PENDING' and _PINNED_NATIVE_IO[id(token)][0] is api
        with pytest.raises(NativeSerialError): api.close_handle(handle)
        token.payload = b'changed'
        with pytest.raises(NativeSerialError): api.complete_io(handle,token,100)
        token.payload = kernel.writes[0]
        assert api.complete_io(handle,token,100).state == 'COMPLETE'
        assert id(token) not in _PINNED_NATIVE_IO
    finally:
        # Test-owned fake storage only; never clear another token/provider's pin.
        _PINNED_NATIVE_IO.pop(id(token),None)


def test_unadmitted_constructor_stays_held_without_loading_kernel(monkeypatch):
    monkeypatch.setattr(WindowsNativeSerialApi,'_load_kernel',lambda *_:pytest.fail('No kernel load'))
    with pytest.raises(NativeSerialError): WindowsEndpointSerialApi('COM7').create_file('\\\\.\\COM7')


def test_revoked_permit_cannot_load_native_kernel(tmp_path,monkeypatch):
    req, authority, records, raw, filename, reader, tick, current = fixture(tmp_path)
    current[0] = replace(current[0],port_name='COM7')
    permit = authorize_bench_endpoint(req, connection_id='owned-test', evidence_reader=reader,
                                     attempt_root=tmp_path,clock=lambda:tick[0])
    api = WindowsEndpointSerialApi.from_bench_permit(req,permit,port_name='COM7',connection_id='owned-test')
    permit.revoke()
    monkeypatch.setattr(WindowsNativeSerialApi,'_load_kernel',lambda *_:pytest.fail('No kernel load'))
    with pytest.raises(ValueError): api.create_file('\\\\.\\COM7')


def test_wrong_handle_and_unowned_event_do_not_reach_kernel(tmp_path,monkeypatch):
    req, permit, api, handle, token, kernel, _ = admitted(tmp_path,monkeypatch)
    assert permit.consume(req,'owned-test',baseline_acquired_ns=1_000_000_000)
    with pytest.raises(NativeSerialError): api.submit_io(handle+1,token)
    token.event = 999
    with pytest.raises(NativeSerialError): api.submit_io(handle,token)
    assert kernel.writes == []
