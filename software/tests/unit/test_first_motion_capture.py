"""Fixed commissioning acquisition with synthetic readers and no native I/O."""
from threading import Event

import pytest

from rocell.application.first_motion_capture import capture_first_motion_window
from rocell.application.endpoint_capture import capture_endpoint_window
from test_first_motion_measurement_binding import setup
from test_endpoint_capture import raw


def capture(tmp_path, reader, *, phase='baseline', event=None, start=None):
    _, request = setup(tmp_path)
    tick = [2_000_000_000 if start is None else start]
    return capture_first_motion_window(request,phase,
        read_once=lambda n,t:reader(n,t,tick), cancellation=event or Event(),
        clock_ns=lambda:tick[0], idle_wait=lambda _:None,
        command_completed_ns=2_000_000_000 if phase=='post' else None)


@pytest.mark.parametrize('phase,duration',[('baseline',1_000_000_000),('post',5_000_000_000)])
def test_fixed_window_and_distinct_schema(tmp_path,phase,duration):
    def read(n,t,tick):
        tick[0] += t*1_000_000
        return b''
    result = capture(tmp_path,read,phase=phase)
    assert result['schema'] == 'rocell.first_motion_capture_window.v1'
    assert result['status'] == 'WINDOW_COMPLETE'
    assert result['finished_ns'] == 2_000_000_000+duration
    assert not result['sample_freshness_verified']


@pytest.mark.parametrize('phase,capacity',[('baseline',32768),('post',65536)])
def test_fixed_capacity(tmp_path,phase,capacity):
    result = capture(tmp_path,lambda n,t,tick:b'x'*n,phase=phase)
    assert result['status'] == 'BYTE_CAPACITY_REACHED'
    assert len(raw(result)) == capacity


def test_cancel_retains_bytes(tmp_path):
    event = Event()
    def read(n,t,tick):
        tick[0] += 1
        event.set()
        return b'partial'
    result = capture(tmp_path,read,event=event)
    assert result['status'] == 'CANCELLED' and raw(result) == b'partial'


def test_late_bytes_are_retained(tmp_path):
    def read(n,t,tick):
        tick[0] += 2_000_000_000
        return b'late'
    result = capture(tmp_path,read)
    assert result['status'] == 'READ_COMPLETED_AFTER_WINDOW'
    assert result['late_completion_bytes'] == 4 and raw(result) == b'late'


def test_empty_nonadvancing_reader_has_finite_work(tmp_path):
    result = capture(tmp_path,lambda n,t,tick:b'')
    assert result['status'] == 'READ_CALL_LIMIT_REACHED' and result['read_calls'] == 256


def test_delayed_post_start_does_not_extend_window(tmp_path):
    def read(n,t,tick):
        tick[0] += t*1_000_000
        return b''
    result = capture(tmp_path,read,phase='post',start=3_000_000_000)
    assert result['window_deadline_ns'] == 7_000_000_000


def test_commissioning_request_cannot_enter_endpoint_collector(tmp_path):
    _, request = setup(tmp_path)
    with pytest.raises(ValueError):
        capture_endpoint_window(request,'baseline',read_once=lambda *_:pytest.fail('read'),
                                cancellation=Event())
