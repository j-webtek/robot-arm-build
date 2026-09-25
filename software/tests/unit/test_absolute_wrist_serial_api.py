"""Exercise exact absolute native-boundary checks with a fake kernel only."""
import math

import pytest

from rocell.providers.windows.absolute_wrist_serial_api import WindowsAbsoluteWristSerialApi
from rocell.providers.windows.absolute_wrist_serial_connection import AbsoluteWristSerialConnection
from rocell.providers.windows.observational_serial_api import WindowsObservationalSerialApi
from rocell.providers.windows.nonpurging_serial_api import WindowsNativeSerialApi, IoToken, NativeSerialError
from rocell.safety.absolute_wrist_admission import admit_absolute_wrist, AbsoluteWristPermit
from test_absolute_wrist_binding import fixture
from test_endpoint_serial_api import FakeKernel
from test_first_motion_analysis import wire


def admitted(tmp_path, monkeypatch, select=True):
    request, reader, clock, refs, _ = fixture(tmp_path)
    permit = admit_absolute_wrist(request, reader=reader, root=tmp_path)
    kernel = FakeKernel()
    def load(api):
        api._dll = kernel
        return kernel
    monkeypatch.setattr(WindowsNativeSerialApi, '_load_kernel', load)
    port = permit._binding._port
    api = WindowsAbsoluteWristSerialApi.from_absolute_wrist_permit(request, permit,
        port_name=port, connection_id=request.to_dict()['attempt_id'])
    handle = api.create_file('\\\\.\\' + port)
    event = api.create_event()
    if select:
        raw, windows = wire([math.radians(-4)] * 10, 2_000_000_000)
        clock[0] = 2_500_000_000
        permit.bind_owned_baseline(request, api.connection_id, port, raw, windows,
                                   started_ns=2_000_000_000, finished_ns=2_500_000_000)
    return request, permit, api, handle, event, kernel, clock, refs


def test_exact_target_only_once_at_native_boundary(tmp_path, monkeypatch):
    request, permit, api, handle, event, kernel, *_ = admitted(tmp_path, monkeypatch)
    payload = permit.selected_payload()
    token = IoToken(event, 'write', len(payload), payload)
    result = api.submit_io(handle, token)
    assert result.state == 'COMPLETE' and result.transferred == len(payload)
    assert kernel.writes == [payload]
    with pytest.raises(NativeSerialError): api.submit_io(handle, token)
    with pytest.raises(ValueError): permit.claim_native_dispatch(request, api.connection_id, api._port_name)
    api.close_handle(event)
    api.close_handle(handle)


@pytest.mark.parametrize('payload', [b'{"T":0}\n', b'{"T":999}\n', b'{"T":105}\n',
    b'{"T":101,"joint":4,"rad":0.1,"spd":20,"acc":1}\n',
    b'{"T":101,"joint":4,"rad":0.0,"spd":40,"acc":1}\n'])
def test_changed_native_bytes_burn_write_without_submission(tmp_path, monkeypatch, payload):
    _, permit, api, handle, event, kernel, *_ = admitted(tmp_path, monkeypatch)
    with pytest.raises(NativeSerialError): api.submit_io(handle, IoToken(event, 'write', len(payload), payload))
    correct = permit.selected_payload()
    with pytest.raises(NativeSerialError): api.submit_io(handle, IoToken(event, 'write', len(correct), correct))
    assert not kernel.writes
    permit.revoke()
    api.close_handle(event)
    api.close_handle(handle)


@pytest.mark.parametrize('fault', ['stale', 'references', 'revoked'])
def test_context_failure_before_writefile(tmp_path, monkeypatch, fault):
    _, permit, api, handle, event, kernel, clock, refs = admitted(tmp_path, monkeypatch)
    payload = permit.selected_payload()
    if fault == 'stale': clock[0] += 300_000_000
    if fault == 'references': refs[0] = ()
    if fault == 'revoked': permit.revoke()
    with pytest.raises(ValueError): api.submit_io(handle, IoToken(event, 'write', len(payload), payload))
    assert not kernel.writes
    api.close_handle(event)
    api.close_handle(handle)


def test_no_baseline_no_native_command(tmp_path, monkeypatch):
    _, permit, api, handle, event, kernel, *_ = admitted(tmp_path, monkeypatch, select=False)
    with pytest.raises(ValueError): permit.selected_payload()
    with pytest.raises(ValueError): api.submit_io(handle, IoToken(event, 'write', 1, b'x'))
    assert not kernel.writes
    api.close_handle(event)
    api.close_handle(handle)


def test_cross_domain_and_unadmitted_construction_remain_held(tmp_path, monkeypatch):
    request, reader, _, _, _ = fixture(tmp_path)
    permit = admit_absolute_wrist(request, reader=reader, root=tmp_path)
    monkeypatch.setattr(WindowsNativeSerialApi, '_load_kernel', lambda *_: pytest.fail('No native kernel load'))
    with pytest.raises(ValueError):
        WindowsObservationalSerialApi.from_observational_permit(request, permit,
            port_name='COM7', connection_id=request.to_dict()['attempt_id'])
    with pytest.raises(ValueError): AbsoluteWristPermit(object(), request, permit._binding)
    with pytest.raises(NativeSerialError): WindowsAbsoluteWristSerialApi('COM7').create_file('\\\\.\\COM7')
    with pytest.raises(ValueError): AbsoluteWristSerialConnection(request, WindowsAbsoluteWristSerialApi('COM7'))
