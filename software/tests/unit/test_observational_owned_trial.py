import json
from threading import Event

import pytest

from rocell.application.observational_owned_trial import run_owned_observational_trial
from rocell.application.observational_capture import capture_observational_window, validate_clean_observational_capture
from rocell.application.endpoint_owned_trial import EndpointCleanupResult
from test_observational_admission import prepared


def run(tmp_path, fault=None):
    request, permit, reader, snapshots, clock, port = prepared(tmp_path)
    connection = request.to_dict()['attempt_id']
    permit.claim_native_open(request, connection, port)
    event = Event()
    calls = dict(read=0, write=0, close=0)
    angle = [.02]
    if fault == 'cancel_before': event.set()
    def read(size, timeout):
        calls['read'] += 1
        clock[0] += min(50, timeout)*1_000_000
        if fault == 'bad_baseline' and not calls['write']: return b'bad\n'
        fields = dict(T=1051, x=1, y=2, z=3, tit=0, b=0, s=0, e=0,
                      t=angle[0], r=0, g=0)
        raw = json.dumps(fields, separators=(',', ':')).encode()+b'\n'
        assert len(raw) <= size
        return raw
    def write(payload):
        calls['write'] += 1
        permit.claim_native_dispatch(request, connection, port)
        angle[0] = json.loads(payload)['rad']
        if fault == 'write_error': raise OSError('synthetic failure')
        if fault == 'cancel_after': event.set()
        return len(payload)-1 if fault == 'short_write' else len(payload)
    def close(timeout):
        calls['close'] += 1
        assert timeout == 2000
        if fault == 'close_error': raise OSError('synthetic cleanup failure')
        return EndpointCleanupResult(True, 0)
    result = run_owned_observational_trial(request, permit, connection_id=connection,
        port_name=port, read_once=read, write_once=write, close_once=close,
        cancellation=event, basis='SYNTHETIC_WIRE_REHEARSAL', clock_ns=lambda: clock[0],
        idle_wait=lambda seconds: clock.__setitem__(0, clock[0]+round(seconds*1e9)))
    return request, result, calls


def test_full_bounded_sequence_retains_captures_and_awaits_observation(tmp_path):
    request, result, calls = run(tmp_path)
    assert result['status'] == 'AWAITING_OPERATOR_OBSERVATION'
    assert calls == dict(read=118, write=1, close=1)
    assert result['cleanup']['status'] == 'HANDLES_CLOSED'
    assert result['physical_movement_verified'] is False
    assert result['campaign_advance_allowed'] is False
    for phase in ('baseline', 'post'):
        assert validate_clean_observational_capture(request, result[phase], phase=phase,
            command_completed_ns=result['write']['write_finished_ns'] if phase == 'post' else None)


@pytest.mark.parametrize('fault', [None, 'late', 'cancel_tail'])
def test_capture_tail_preserves_deadline_and_faults(tmp_path, fault):
    request, _, _, _, clock, _ = prepared(tmp_path)
    event = Event()
    started = clock[0]
    reads = []
    def read(size, timeout):
        reads.append((clock[0], timeout))
        clock[0] += (1100 if fault == 'late' else 20)*1_000_000
        return b'{}\n'
    def wait(seconds):
        clock[0] += round(seconds*1e9)
        if fault == 'cancel_tail':
            event.set()
    capture = capture_observational_window(request, 'baseline', read_once=read,
        cancellation=event, clock_ns=lambda: clock[0], idle_wait=wait)
    assert capture['window_deadline_ns'] == started+1_000_000_000
    assert all(t < started+950_000_000 and timeout >= 25 for t, timeout in reads)
    if fault == 'late':
        assert capture['status'] == 'READ_COMPLETED_AFTER_WINDOW'
        assert capture['raw']['bytes'] == capture['late_completion_bytes'] == 3
    elif fault == 'cancel_tail':
        assert capture['status'] == 'CANCELLED'
    else:
        assert capture['status'] == 'WINDOW_COMPLETE'
        assert capture['finished_ns'] == capture['window_deadline_ns']
        assert capture['late_completion_bytes'] == 0


@pytest.mark.parametrize('fault,status,writes', [
    ('cancel_before', 'CANCELLED_BEFORE_WRITE', 0),
    ('bad_baseline', 'HELD_BEFORE_WRITE', 0),
    ('short_write', 'WRITE_UNCERTAIN_NO_RETRY', 1),
    ('write_error', 'WRITE_UNCERTAIN_NO_RETRY', 1),
    ('cancel_after', 'POST_CAPTURE_INCOMPLETE', 1),
    ('close_error', 'CLEANUP_UNCERTAIN', 1),
])
def test_faults_no_retry_and_cleanup_attempted(tmp_path, fault, status, writes):
    _, result, calls = run(tmp_path, fault)
    assert result['status'] == status
    assert calls['write'] == writes
    assert calls['close'] == 1
    if fault in ('short_write', 'write_error'):
        assert result['post']['status'] == 'WINDOW_COMPLETE'
        assert result['write']['write_completion_uncertain'] is True
