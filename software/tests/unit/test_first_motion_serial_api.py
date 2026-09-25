"""Real admission with synthetic evidence and a fake kernel; no hardware I/O."""
import ctypes
from dataclasses import replace

import pytest

from rocell.arm.protocol import encode_line
from rocell.providers.windows.first_motion_serial_api import WindowsFirstMotionSerialApi
from rocell.providers.windows.endpoint_serial_api import WindowsEndpointSerialApi
from rocell.providers.windows.nonpurging_serial_api import (
    WindowsNativeSerialApi, IoToken, NativeSerialError, _PINNED_NATIVE_IO,
)
from test_first_motion_admission import setup, admit
from test_endpoint_serial_api import FakeKernel


def opened(tmp_path, monkeypatch):
    request, reader, clock, _ = setup(tmp_path)
    permit = admit(tmp_path, request, reader, clock)
    kernel = FakeKernel()
    def load(api):
        api._dll = kernel
        return kernel
    monkeypatch.setattr(WindowsNativeSerialApi, '_load_kernel', load)
    connection = request.to_dict()['attempt_id']
    api = WindowsFirstMotionSerialApi.from_first_motion_permit(
        request, permit, port_name='COM7', connection_id=connection)
    handle = api.create_file(api.expected_path)
    payload = encode_line(request.to_dict()['command'])
    token = IoToken(api.create_event(), 'write', len(payload), payload)
    return request, reader, clock, permit, api, handle, token, kernel, connection


def test_exact_wrist_payload_once(tmp_path, monkeypatch):
    r, _, clock, p, api, handle, token, kernel, conn = opened(tmp_path, monkeypatch)
    assert p.consume_for_write(r, conn, baseline_acquired_ns=clock[0])
    result = api.submit_io(handle, token)
    assert result.state == 'COMPLETE' and result.transferred == token.size
    assert kernel.writes == [encode_line(r.to_dict()['command'])]
    with pytest.raises(NativeSerialError): api.submit_io(handle, token)
    with pytest.raises(NativeSerialError): api.create_file(api.expected_path)
    api.close_handle(token.event)
    api.close_handle(handle)


@pytest.mark.parametrize('payload', [b'{"T":104}\n', b'{"T":999}\n', b'{"T":105}\n',
                                    b'{"T":101,"joint":4,"rad":0,"spd":0,"acc":0}\n'])
def test_other_payloads_burn_write_attempt(tmp_path, monkeypatch, payload):
    r, _, clock, p, api, handle, token, kernel, conn = opened(tmp_path, monkeypatch)
    assert p.consume_for_write(r, conn, baseline_acquired_ns=clock[0])
    correct = token.payload
    token.payload, token.size = payload, len(payload)
    with pytest.raises(NativeSerialError): api.submit_io(handle, token)
    token.payload, token.size = correct, len(correct)
    with pytest.raises(NativeSerialError): api.submit_io(handle, token)
    assert kernel.writes == []


def test_unconsumed_permission_cannot_write(tmp_path, monkeypatch):
    r, _, clock, p, api, handle, token, kernel, conn = opened(tmp_path, monkeypatch)
    with pytest.raises(ValueError): api.submit_io(handle, token)
    assert p.consume_for_write(r, conn, baseline_acquired_ns=clock[0])
    with pytest.raises(NativeSerialError): api.submit_io(handle, token)
    assert kernel.writes == []


def test_changed_port_stops_dispatch(tmp_path, monkeypatch):
    r, reader, clock, p, api, handle, token, kernel, conn = opened(tmp_path, monkeypatch)
    assert p.consume_for_write(r, conn, baseline_acquired_ns=clock[0])
    original = reader._context
    reader._context = lambda: replace(original(), port_name='COM8')
    with pytest.raises(ValueError): api.submit_io(handle, token)
    assert kernel.writes == []


def test_pending_storage_retained_until_completion(tmp_path, monkeypatch):
    r, _, clock, p, api, handle, token, kernel, conn = opened(tmp_path, monkeypatch)
    assert p.consume_for_write(r, conn, baseline_acquired_ns=clock[0])
    kernel.pending = True
    monkeypatch.setattr(ctypes, 'get_last_error', lambda:997, raising=False)
    try:
        assert api.submit_io(handle, token).state == 'PENDING'
        assert _PINNED_NATIVE_IO[id(token)][0] is api
        with pytest.raises(NativeSerialError): api.close_handle(handle)
        assert api.complete_io(handle, token, 100).state == 'COMPLETE'
        assert id(token) not in _PINNED_NATIVE_IO
    finally:
        _PINNED_NATIVE_IO.pop(id(token), None)  # Only this test's fake storage.


def test_inert_constructor_and_wrong_factory_have_no_kernel_access(tmp_path, monkeypatch):
    monkeypatch.setattr(WindowsNativeSerialApi, '_load_kernel', lambda *_:pytest.fail('DLL access'))
    with pytest.raises(NativeSerialError):
        WindowsFirstMotionSerialApi('COM7').create_file('\\\\.\\COM7')
    r, reader, clock, _ = setup(tmp_path)
    p = admit(tmp_path, r, reader, clock)
    for facade in (WindowsEndpointSerialApi, WindowsFirstMotionSerialApi):
        with pytest.raises(ValueError):
            facade.from_bench_permit(r, p, port_name='COM7', connection_id=r.to_dict()['attempt_id'])
    with pytest.raises(ValueError):
        WindowsFirstMotionSerialApi.from_first_motion_permit(
            r, object(), port_name='COM7', connection_id=r.to_dict()['attempt_id'])


def test_short_write_is_reported_without_retry(tmp_path, monkeypatch):
    r, _, clock, p, api, handle, token, kernel, conn = opened(tmp_path, monkeypatch)
    assert p.consume_for_write(r, conn, baseline_acquired_ns=clock[0])
    def short_result(handle, overlapped, count, timeout, alertable):
        count._obj.value = token.size - 1
        return True
    kernel.GetOverlappedResultEx = short_result
    result = api.submit_io(handle, token)
    assert result.transferred == token.size - 1
    with pytest.raises(NativeSerialError): api.submit_io(handle, token)
    assert len(kernel.writes) == 1
    # The worker must classify this as inconclusive, not successful movement.


def test_uncertain_syscall_keeps_storage_and_prevents_retry(tmp_path, monkeypatch):
    r, _, clock, p, api, handle, token, kernel, conn = opened(tmp_path, monkeypatch)
    assert p.consume_for_write(r, conn, baseline_acquired_ns=clock[0])
    def uncertain(*args):
        raise OSError('synthetic uncertain submission')
    kernel.WriteFile = uncertain
    try:
        with pytest.raises(OSError): api.submit_io(handle, token)
        assert _PINNED_NATIVE_IO[id(token)][0] is api
        with pytest.raises(NativeSerialError): api.submit_io(handle, token)
        with pytest.raises(NativeSerialError): api.close_handle(handle)
    finally:
        _PINNED_NATIVE_IO.pop(id(token), None)
