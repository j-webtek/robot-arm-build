"""Bound fragmented USB reads without increasing byte, call or time budgets."""
from threading import Event

import pytest

from rocell.application.observational_capture import capture_observational_window
from rocell.safety.observational_review_authority import ObservationalIntent
from rocell.application.first_motion_contract import canonical
from test_observational_review_authority import intent


@pytest.mark.parametrize('latency_ms', [0, 1, 7, 16])
def test_fragmented_reads_fill_fixed_window_without_exhausting_calls(latency_ms):
    request = ObservationalIntent(canonical(intent()))
    clock = [2_000_000_000]
    starts = []
    def read(size, timeout):
        starts.append(clock[0])
        clock[0] += latency_ms*1_000_000
        return b'x'*64  # Arbitrary retained bytes, not invented valid telemetry.
    result = capture_observational_window(request, 'post', read_once=read,
        cancellation=Event(), command_completed_ns=clock[0], clock_ns=lambda: clock[0],
        idle_wait=lambda seconds: clock.__setitem__(0, clock[0]+round(seconds*1e9)))
    assert result['status'] == 'WINDOW_COMPLETE'
    assert result['finished_ns'] == result['window_deadline_ns'] == 7_000_000_000
    assert result['read_calls'] <= 500 < request.runtime_body()['limits']['maximum_post_reads']
    assert all(b-a >= 10_000_000 for a,b in zip(starts, starts[1:]))
    assert result['raw']['bytes'] == len(starts)*64
    assert result['physical_movement_verified'] is False


def test_cancel_during_pacing_stops_before_next_read():
    request = ObservationalIntent(canonical(intent()))
    clock, reads, event = [2_000_000_000], [], Event()
    def read(size, timeout):
        reads.append(clock[0])
        return b'x'
    def wait(seconds):
        event.set()
    result = capture_observational_window(request, 'baseline', read_once=read,
        cancellation=event, clock_ns=lambda: clock[0], idle_wait=wait)
    assert result['status'] == 'CANCELLED'
    assert len(reads) == 1 and result['raw']['bytes'] == 1


def test_fast_stream_still_hits_unchanged_byte_cap():
    request = ObservationalIntent(canonical(intent()))
    clock = [2_000_000_000]
    result = capture_observational_window(request, 'post', read_once=lambda size, timeout: b'x'*size,
        cancellation=Event(), command_completed_ns=clock[0], clock_ns=lambda: clock[0],
        idle_wait=lambda seconds: clock.__setitem__(0, clock[0]+round(seconds*1e9)))
    assert result['status'] == 'BYTE_CAPACITY_REACHED'
    assert result['raw']['bytes'] == 65536
    assert result['finished_ns'] < result['window_deadline_ns']
