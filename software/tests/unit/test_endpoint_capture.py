"""Capture work/storage limits without a device, wall-clock wait or write API."""

import base64
import hashlib
from threading import Event

import pytest

from rocell.application.endpoint_capture import capture_endpoint_window
from test_endpoint_trial_contract import request


def capture(reader, *, phase='post', event=None, tick=None):
    tick = [1_000_000_000] if tick is None else tick
    return capture_endpoint_window(request(),phase,read_once=lambda n,t:reader(n,t,tick),
        cancellation=event or Event(),clock_ns=lambda:tick[0],idle_wait=lambda _:None,
        command_completed_ns=1_000_000_000 if phase=='post' else None)


def raw(result):
    return b''.join(base64.b64decode(chunk,validate=True) for chunk in result['raw']['base64_chunks'])


def test_data_and_read_bounds_survive_cancellation():
    event = Event()
    def reader(n,t,tick):
        assert n <= 256 and 1 <= t <= 100
        tick[0] += 1_000_000
        event.set()
        return b'partial-pose'
    result = capture(reader,event=event)
    assert result['status'] == 'CANCELLED'
    assert raw(result) == b'partial-pose'
    assert result['coverage']['unprocessed_range'] == [0,12]
    assert result['read_calls'] == 1
    assert not result['physical_stop_verified']


@pytest.mark.parametrize('phase,capacity', [('baseline',32768),('post',65536)])
def test_capacity_stops_without_truncating_or_purging(phase,capacity):
    result = capture(lambda n,t,tick:b'x'*n,phase=phase)
    assert result['status'] == 'BYTE_CAPACITY_REACHED'
    assert len(raw(result)) == capacity
    assert result['read_calls'] == capacity//256
    assert result['raw']['sha256'] == hashlib.sha256(raw(result)).hexdigest()


def test_empty_immediate_reader_is_bounded_by_call_count():
    result = capture(lambda n,t,tick:b'')
    assert result['status'] == 'READ_CALL_LIMIT_REACHED'
    assert result['read_calls'] == 512 and result['raw']['bytes'] == 0


def test_normal_elapsed_window_does_not_claim_valid_pose():
    def reader(n,t,tick):
        tick[0] += t*1_000_000
        return b''
    result = capture(reader)
    assert result['status'] == 'WINDOW_COMPLETE'
    assert result['finished_ns'] == 3_000_000_000  # selected trial's 2-second timeout
    assert result['coverage']['counts']['POSE_TELEMETRY'] == 0


def test_late_completion_retained_but_excluded_from_on_time_count():
    def reader(n,t,tick):
        tick[0] += 2_100_000_000
        return b'late\n'
    result = capture(reader)
    assert result['status'] == 'READ_COMPLETED_AFTER_WINDOW'
    assert raw(result) == b'late\n'
    assert result['within_deadline_bytes'] == 0 and result['late_completion_bytes'] == 5


def test_broken_reader_cannot_expand_capture_budget():
    result = capture(lambda n,t,tick:b'x'*(n+1))
    assert result['status'] == 'READER_CONTRACT_VIOLATION'
    assert result['raw']['bytes'] == 0
    assert not result['abnormal_completion']['complete_original_retained']


def test_clock_failure_after_read_preserves_untimed_original():
    def reader(n,t,tick):
        tick[0] -= 1
        return b'returned-before-clock-failed'
    result = capture(reader)
    original = result['untimed_completion']
    assert base64.b64decode(original['base64']) == b'returned-before-clock-failed'
    assert result['read_windows'] == []
    assert result['status'] == 'CAPTURE_FAILED'


def test_reader_exception_preserves_prior_capture_and_omits_external_text():
    count = 0
    def reader(n,t,tick):
        nonlocal count
        count += 1
        if count == 2:
            raise RuntimeError('private driver details')
        tick[0] += 1_000_000
        return b'prior\n'
    result = capture(reader)
    assert result['status'] == 'CAPTURE_FAILED'
    assert result['errors'] == ['RuntimeError']
    assert raw(result) == b'prior\n'


def test_collected_endpoint_is_reanalyzed_and_fault_status_cannot_qualify():
    from copy import deepcopy
    from rocell.application.endpoint_capture import analyze_endpoint_capture
    line = b'{"T":1051,"x":1,"y":0,"z":0,"tit":0,"r":0,"g":0,"b":0,"s":0,"e":0,"t":0}\n'
    def reader(n,t,tick):
        tick[0] += 50_000_000
        return line
    result = capture(reader,tick=[1_050_000_000])
    assert result['status'] == 'WINDOW_COMPLETE'
    analysis = analyze_endpoint_capture(request(),result,command_completed_ns=1_000_000_000,
                                        basis='SYNTHETIC_WIRE_REHEARSAL')
    assert analysis['status'] == 'OBSERVED_ENDPOINT_DWELL'
    for status in ('CANCELLED','BYTE_CAPACITY_REACHED','READ_CALL_LIMIT_REACHED'):
        broken = deepcopy(result)
        broken['status'] = status
        analysis = analyze_endpoint_capture(request(),broken,command_completed_ns=1_000_000_000,
                                            basis='SYNTHETIC_WIRE_REHEARSAL')
        assert analysis['status'] == 'INSUFFICIENT_ENDPOINT_EVIDENCE'
        assert analysis['host_endpoint_dwell_entry_bounds_ns'] is None
    result['raw']['sha256'] = 'f'*64
    with pytest.raises(ValueError,match='digest'):
        analyze_endpoint_capture(request(),result,command_completed_ns=1_000_000_000,
                                 basis='SYNTHETIC_WIRE_REHEARSAL')
