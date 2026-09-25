"""Child composition through real admission/collector logic, incapable kernel."""
import ctypes
import json
from threading import Event

import pytest

from rocell.application.first_motion_contract import canonical
from rocell.application.positional_campaign_launch import reserve_campaign_launch
from rocell.providers.windows.nonpurging_serial_api import WindowsNativeSerialApi
from rocell.providers.windows.positional_campaign_child_execution import _execute_authenticated_campaign_child
from test_positional_campaign_launch import setup
from test_positional_campaign_native_protocol import fixture, seal
from test_endpoint_serial_connection import OwnerKernel


def prepared(tmp_path, monkeypatch, mode='complete', *, start_angle=0., response_target_rad=None, selected_axis=3, initial_prefix=b'',fault_leg=1,initial_pose=None):
    reader, runtime = setup(tmp_path)
    evidence = reader.verify_endpoint()
    clock = [evidence['verified_at_ns']]
    reader.verify_endpoint = lambda port=None: dict(evidence, verified_at_ns=clock[0])
    launch = reserve_campaign_launch(tmp_path, reader, runtime_original=runtime)
    wire = fixture(tmp_path)
    body = reader.request.to_dict()
    wire['payload'].update(campaign_intent=body, launch_sha256=launch, registration=json.loads(runtime))
    wire.update(operation_sha256=reader.request.sha256, registration_sha256=body['references']['runtime_sha256'])
    cancellation = Event()
    # The production collector waits on this event between bounded reads.
    # Advance simulated time there as well, including the final idle tail.
    cancellation.wait = lambda seconds: clock.__setitem__(0, clock[0] + round(seconds*1e9))
    kernel = OwnerKernel()
    def load(instance):
        instance._dll = kernel
        return kernel
    monkeypatch.setattr(WindowsNativeSerialApi, '_load_kernel', load)
    monkeypatch.setattr(ctypes, 'get_last_error', lambda: kernel.last_error)
    angles = [0.]*6 if initial_pose is None else list(initial_pose)
    angles[selected_axis] = start_angle
    original_read, original_write = kernel.ReadFile, kernel.WriteFile
    def refresh():
        if not kernel.input:
            kernel.input = canonical(dict(T=1051, x=0, y=0, z=0, tit=0,
                **dict(zip(('b','s','e','t','r','g'),angles)))) + b'\n'
    def read(handle, buffer, size, count, overlapped):
        clock[0] += 20_000_000
        outcome = original_read(handle, buffer, size, count, overlapped)
        kernel.input = kernel.input[kernel.size:]
        refresh()
        return outcome
    def write(handle, buffer, size, count, overlapped):
        outcome = original_write(handle, buffer, size, count, overlapped)
        active_mode=mode if len(kernel.writes)==fault_leg else 'complete'
        if active_mode != 'miss':
            command=json.loads(kernel.writes[-1])
            angles[command['joint']-1] = (command['rad']
                if response_target_rad is None else response_target_rad(command) if callable(response_target_rad) else response_target_rad)
        if active_mode == 'cancel':
            cancellation.set()
        refresh()
        return outcome
    kernel.ReadFile, kernel.WriteFile = read, write
    kernel.input = b''
    refresh()
    kernel.input=initial_prefix+kernel.input
    return reader, seal(wire), kernel, cancellation, clock


@pytest.mark.parametrize('mode,writes,status', [
    ('complete', 2, 'REPORTED_CAMPAIGN_COMPLETE'), ('miss', 1, 'HELD'), ('cancel', 1, 'CANCELLED')])
def test_composition_retains_actual_collector_result_and_cannot_replay(tmp_path, monkeypatch, mode, writes, status):
    reader, raw, kernel, cancellation, clock = prepared(tmp_path, monkeypatch, mode)
    receipt = _execute_authenticated_campaign_child(raw, reader,
        cancellation=cancellation, clock_ns=lambda: clock[0])
    assert len(receipt) < 1024
    compact = json.loads(receipt)
    result = json.loads((tmp_path / (reader.request.to_dict()['campaign_id']+'-native-trial.json')).read_bytes())
    assert result['status'] == status
    assert compact['trial_bytes'] == len(canonical(result))
    assert result['cleanup']['all_handles_closed']
    assert len(kernel.writes) == writes
    assert kernel.closed == [202, 201, 101]
    assert not result['physical_stop_verified'] and not compact['physical_authority']
    cancellation.clear()
    with pytest.raises((ValueError, OSError, RuntimeError)):
        _execute_authenticated_campaign_child(raw, reader, cancellation=cancellation, clock_ns=lambda: clock[0])
    assert len(kernel.writes) == writes


@pytest.mark.parametrize('fault', ['cancel', 'root', 'wire'])
def test_invalid_preparation_never_loads_kernel(tmp_path, monkeypatch, fault):
    reader, raw, kernel, cancellation, clock = prepared(tmp_path, monkeypatch)
    def forbidden(instance):
        pytest.fail('Invalid preparation attempted native access')
    monkeypatch.setattr(WindowsNativeSerialApi, '_load_kernel', forbidden)
    if fault == 'cancel': cancellation.set()
    if fault == 'root':
        wire = json.loads(raw)
        other = tmp_path / 'other'
        other.mkdir()
        wire['payload']['root'] = str(other)
        raw = seal(wire)
    if fault == 'wire': raw = b'{}'
    with pytest.raises(ValueError):
        _execute_authenticated_campaign_child(raw, reader, cancellation=cancellation, clock_ns=lambda: clock[0])
    assert kernel.writes == []


def test_retention_failure_occurs_after_close_and_does_not_rearm(tmp_path, monkeypatch):
    reader, raw, kernel, cancellation, clock = prepared(tmp_path, monkeypatch)
    def fail_retention(*args, **kwargs):
        assert kernel.closed == [202, 201, 101]
        raise OSError('Injected disk failure')
    monkeypatch.setattr('rocell.providers.windows.positional_campaign_child_execution.retain_native_trial',
        fail_retention)
    with pytest.raises(OSError, match='disk failure'):
        _execute_authenticated_campaign_child(raw, reader, cancellation=cancellation, clock_ns=lambda: clock[0])
    with pytest.raises((ValueError, OSError, RuntimeError)):
        _execute_authenticated_campaign_child(raw, reader, cancellation=cancellation, clock_ns=lambda: clock[0])
    assert len(kernel.writes) == 2
