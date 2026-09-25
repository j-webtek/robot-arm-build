import base64
import ctypes

import pytest

from rocell.application.positional_campaign_rehearsal import _capture
from rocell.providers.windows.positional_campaign_serial_connection import PositionalCampaignSerialConnection
from rocell.providers.windows.nonpurging_serial_api import WindowsNativeSerialApi
from test_positional_campaign_serial_api import admitted
from test_positional_campaign_admission import baseline
from test_endpoint_serial_connection import OwnerKernel


def owner(tmp_path, monkeypatch):
    permit, api, _, _, _, clock = admitted(tmp_path, monkeypatch, opened=False)
    kernel = OwnerKernel()
    def load(instance):
        instance._dll = kernel
        return kernel
    monkeypatch.setattr(WindowsNativeSerialApi, '_load_kernel', load)
    monkeypatch.setattr(ctypes, 'get_last_error', lambda: kernel.last_error)
    connection = PositionalCampaignSerialConnection(permit.request, api, clock_ns=lambda: clock[0])
    return permit, api, connection, kernel, clock


def test_two_legs_preserve_phase_counts_and_one_handle_lifecycle(tmp_path, monkeypatch):
    permit, api, connection, kernel, clock = owner(tmp_path, monkeypatch)
    connection.open()
    start = 0.
    for index, leg in enumerate(permit.request.to_dict()['legs']):
        connection.begin_leg(leg['leg_id'])
        assert connection.read(256, 100) == kernel.input
        baseline(permit, clock, start, 3_000_000_000 if index == 0 else 9_100_000_000)
        payload = permit.consume_command()
        finished = clock[0]
        assert connection.write_once(payload) == len(payload)
        assert connection.read(256, 100) == kernel.input
        with pytest.raises(ValueError):
            connection.write_once(payload)
        post = _capture(start, leg['target_rad'], finished + 20_000_000)
        clock[0] = post['finished_ns'] + 20_000_000
        permit.commit_endpoint(base64.b64decode(post['raw_base64']), post['read_windows'],
            started_ns=post['started_ns'], finished_ns=post['finished_ns'],
            confirmed_write_bytes=len(payload), write_finished_ns=finished, write_uncertain=False)
        start = leg['target_rad']
    assert connection.close(2000).all_handles_closed
    snapshot = connection.snapshot()
    assert kernel.closed == [202, 201, 101]
    assert len(kernel.writes) == 2
    assert snapshot['read_calls'] == dict(baseline=2, post=2)
    assert all(leg['read_calls'] == dict(baseline=1, post=1) for leg in snapshot['legs'])
    assert snapshot['confirmed_write_bytes'] == sum(map(len, kernel.writes))
    assert not snapshot['physical_stop_verified']
    assert connection.close(2000).all_handles_closed and len(kernel.closed) == 3
    with pytest.raises(ValueError): connection.open()


def test_next_leg_requires_verified_predecessor(tmp_path, monkeypatch):
    _, _, connection, kernel, _ = owner(tmp_path, monkeypatch)
    connection.open()
    connection.begin_leg('leg-01')
    with pytest.raises(ValueError): connection.begin_leg('leg-02')
    assert kernel.writes == []
    assert connection.close(2000).all_handles_closed


@pytest.mark.parametrize('phase', ['before_open', 'before_write'])
def test_cancellation_withholds_write_and_keeps_cleanup(tmp_path, monkeypatch, phase):
    permit, api, connection, kernel, clock = owner(tmp_path, monkeypatch)
    if phase == 'before_open':
        api._cancellation.set()
        with pytest.raises(Exception): connection.open()
        assert kernel.closed == []
    else:
        connection.open()
        connection.begin_leg('leg-01')
        baseline(permit, clock)
        payload = permit.consume_command()
        api._cancellation.set()
        with pytest.raises(ValueError): connection.write_once(payload)
        api._cancellation.clear()
        with pytest.raises(ValueError): connection.write_once(payload)
    assert connection.close(2000).all_handles_closed
    assert kernel.writes == []


def test_pending_read_keeps_late_cleanup_bytes(tmp_path, monkeypatch):
    _, _, connection, kernel, _ = owner(tmp_path, monkeypatch)
    connection.open()
    connection.begin_leg('leg-01')
    kernel.pending = True
    kernel.completion_ready = False
    with pytest.raises(Exception): connection.read(256, 100)
    assert connection.snapshot()['pending_io_count'] == 1
    assert connection.close(2000).all_handles_closed
    assert base64.b64decode(connection.snapshot()['late_cleanup_read_base64']) == kernel.input


def test_empty_reads_still_consume_leg_budget(tmp_path, monkeypatch):
    _, _, connection, kernel, _ = owner(tmp_path, monkeypatch)
    connection.open()
    connection.begin_leg('leg-01')
    kernel.input = b''
    for _ in range(256):
        assert connection.read(256, 100) == b''
    with pytest.raises(ValueError, match='read budget'):
        connection.read(256, 100)
    assert connection.snapshot()['legs'][0]['read_calls']['baseline'] == 256
    assert connection.close(2000).all_handles_closed


def test_aborted_late_write_does_not_inherit_previous_byte_count(tmp_path, monkeypatch):
    permit, _, connection, kernel, clock = owner(tmp_path, monkeypatch)
    connection.open()
    connection.begin_leg('leg-01')
    baseline(permit, clock)
    payload = permit.consume_command()
    connection._write_bytes = 123  # Exercise the inherited late-completion slot.
    kernel.pending = True
    kernel.completion_ready = False
    with pytest.raises(Exception): connection.write_once(payload)
    kernel.GetOverlappedResultEx = lambda *args: False
    monkeypatch.setattr(ctypes, 'get_last_error', lambda: 995)
    assert connection.close(2000).all_handles_closed
    assert connection.snapshot()['legs'][0]['confirmed_write_bytes'] == 0
    assert connection.snapshot()['confirmed_write_bytes'] == 0
