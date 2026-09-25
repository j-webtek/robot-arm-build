"""Full collector/admission/facade/owner loop on an incapable streamed kernel."""
import json

import pytest

from rocell.application.first_motion_contract import canonical
from rocell.providers.windows.positional_campaign_execution import run_native_campaign
from test_positional_campaign_serial_connection import owner


def exercise(tmp_path, monkeypatch, *, missed_leg=None, cancel_after_write=False,
        fragment_size=None, failure=None, response_target_rad=None, initial_prefix=b'',
        delayed_response_target_rad=None):
    permit, api, connection, kernel, clock = owner(tmp_path, monkeypatch)
    request = permit.request
    angles = list(request.to_dict()['start_joints_rad'])
    original_read, original_write = kernel.ReadFile, kernel.WriteFile
    write_clock = [None]
    def refresh():
        if not kernel.input:
            if failure=='malformed' and kernel.writes:
                kernel.input=b'bad\n'
                return
            kernel.input = canonical(dict(T=1051, x=0, y=0, z=0, tit=0,
                **dict(zip(('b','s','e','t','r','g'),angles)))) + b'\n'
    def read(handle, buffer, size, count, overlapped):
        # Model timed delivery (50-Hz whole packets or 100-Hz fragments), not
        # post-hoc point timestamps or a supplied precomputed verdict.
        clock[0] += 10_000_000 if fragment_size else 20_000_000
        if (delayed_response_target_rad is not None and write_clock[0] is not None
                and clock[0]-write_clock[0]>=10_000_000_000):
            angles[4]=delayed_response_target_rad
        if failure=='late' and kernel.writes:clock[0]+=300_000_000
        result = original_read(handle, buffer, min(size, fragment_size) if fragment_size else size,
            count, overlapped)
        if failure == 'read_error':
            raise OSError('Injected read failure after possible submission')
        kernel.input = kernel.input[kernel.size:]
        refresh()
        return result
    def write(handle, buffer, size, count, overlapped):
        write_clock[0]=clock[0]
        result = original_write(handle, buffer, size, count, overlapped)
        if failure == 'write_error':
            raise OSError('Injected write failure after possible submission')
        if len(kernel.writes) != missed_leg:
            command=json.loads(kernel.writes[-1])
            angles[command['joint']-1] = (command['rad']
                if response_target_rad is None else response_target_rad)
        refresh()
        if cancel_after_write:
            api._cancellation.set()
        if failure=='other_joint':angles[2]+=.02
        if failure=='short_write':count._obj.value=max(0,size-1)
        return result
    kernel.ReadFile, kernel.WriteFile = read, write
    if failure == 'setup_error':
        kernel.fail_setup = True
    if failure == 'cancel_before_open':
        api._cancellation.set()
    kernel.input = b''
    refresh()
    kernel.input = initial_prefix + kernel.input
    result = run_native_campaign(request, permit, connection, cancellation=api._cancellation,
        clock_ns=lambda: clock[0],
        idle_wait=lambda seconds: clock.__setitem__(0, clock[0] + round(seconds*1e9)))
    captures = [leg[phase] for leg in result['legs'] for phase in ('baseline', 'post') if leg[phase] is not None]
    verdicts = [leg['verification'] for leg in result['legs'] if leg['verification'] is not None]
    assert result['cleanup']['all_handles_closed'], result
    assert result['native_submission_attempts'] == len(kernel.writes)
    return kernel, captures, verdicts, result['lifecycle'], result


@pytest.mark.parametrize('fragment_size', [None, 23, 37])
def test_streamed_two_leg_native_shaped_loop_matches_lifecycle_accounting(tmp_path, monkeypatch, fragment_size):
    kernel, captures, verdicts, lifecycle, result = exercise(tmp_path, monkeypatch, fragment_size=fragment_size)
    assert result['status'] == 'REPORTED_CAMPAIGN_COMPLETE', result
    assert result['errors'] == []
    assert result['skipped_leg_ids'] == []
    assert not result['native_execution_released'] and not result['physical_movement_verified']
    assert len(kernel.writes) == 2 and len(captures) == 4
    assert [v['state'] for v in verdicts] == ['OPEN_CLAIMED', 'COMPLETE']
    assert all(v['endpoint']['endpoint_verified'] for v in verdicts)
    for index, leg in enumerate(lifecycle['legs']):
        for offset, phase in enumerate(('baseline', 'post')):
            capture = captures[2*index + offset]
            assert capture['status'] == 'WINDOW_COMPLETE'
            assert leg['read_calls'][phase] == capture['read_calls']
            assert leg['read_bytes'][phase] == capture['raw']['bytes']
    assert kernel.closed == [202, 201, 101]
    assert lifecycle['pending_io_count'] == lifecycle['owned_handle_count'] == 0
    assert not lifecycle['physical_stop_verified']


@pytest.mark.parametrize('missed_leg', [1, 2])
def test_streamed_target_miss_prevents_later_native_shaped_command(tmp_path, monkeypatch, missed_leg):
    kernel, captures, verdicts, lifecycle, result = exercise(tmp_path, monkeypatch, missed_leg=missed_leg)
    assert result['status'] == 'HELD'
    assert len(result['skipped_leg_ids']) == 2 - missed_leg
    assert len(kernel.writes) == missed_leg
    assert len(captures) == missed_leg * 2
    assert verdicts[-1]['state'] == 'HELD'
    assert not verdicts[-1]['endpoint']['endpoint_verified']
    assert lifecycle['phase'] == 'CLOSED'


def test_cancel_after_native_shaped_write_closes_without_second_command(tmp_path, monkeypatch):
    kernel, captures, verdicts, lifecycle, result = exercise(tmp_path, monkeypatch, cancel_after_write=True)
    assert result['status'] == 'CANCELLED'
    assert len(kernel.writes) == 1
    assert captures[-1]['status'] == 'CANCELLED'
    assert verdicts == []
    assert lifecycle['phase'] == 'CLOSED'


@pytest.mark.parametrize('failure,writes', [
    ('setup_error', 0), ('read_error', 0), ('write_error', 1), ('cancel_before_open', 0)])
def test_runner_failures_retain_outcome_and_close_without_retry(tmp_path, monkeypatch, failure, writes):
    kernel, captures, verdicts, lifecycle, result = exercise(tmp_path, monkeypatch, failure=failure)
    assert result['status'] == ('CANCELLED' if failure == 'cancel_before_open' else 'HELD')
    assert len(kernel.writes) == writes
    assert verdicts == []
    assert lifecycle['owned_handle_count'] == lifecycle['pending_io_count'] == 0
    assert len(set(kernel.closed)) == len(kernel.closed)
    assert result['physical_stop_verified'] is False
    if failure == 'write_error':
        assert result['legs'][0]['write']['uncertain'] is True
        assert result['legs'][0]['write']['finished_ns'] is None
        assert result['lifecycle']['confirmed_write_bytes'] == len(kernel.writes[0])
