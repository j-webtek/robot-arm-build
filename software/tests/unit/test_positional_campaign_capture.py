"""Exercise campaign-specific collector limits with incapable readers."""

import base64
from threading import Event

import pytest

from rocell.application.positional_campaign_capture import capture_campaign_window, validate_campaign_capture
from test_positional_campaign_admission import setup


@pytest.mark.parametrize('phase,expected_reads,read_limit', [
    ('baseline', 95, 256), ('post', 495, 512)])
@pytest.mark.parametrize('block', [b'', b'x'])
def test_immediate_small_reads_are_paced_within_fixed_campaign_budget(
        tmp_path, phase, expected_reads, read_limit, block):
    """Exercise actual pacing, without shrinking limits to force a failure.

    Ten-ms read spacing plus the 50-ms final guard bounds call count more
    tightly than the absolute cap. Empty reads must not spin or extend time.
    """
    _, reader, clock = setup(tmp_path)
    start = clock[0]
    begins = []
    def read(size, timeout):
        begins.append(clock[0])
        assert size <= 256 and 0 < timeout <= 100
        return block
    result = capture_campaign_window(reader.request, phase, read_once=read,
        cancellation=Event(), clock_ns=lambda: clock[0],
        idle_wait=lambda seconds: clock.__setitem__(0, clock[0] + round(seconds * 1e9)),
        command_completed_ns=start if phase == 'post' else None)
    assert result['status'] == 'WINDOW_COMPLETE'
    assert result['read_calls'] == len(begins) == expected_reads
    assert len(begins) < read_limit
    assert all(b - a >= 10_000_000 for a, b in zip(begins, begins[1:]))
    assert result['finished_ns'] == start + (1 if phase == 'baseline' else 5) * 1_000_000_000
    assert result['raw']['bytes'] == expected_reads * len(block)
    assert result['late_completion_bytes'] == 0
    # A clean capture window is not an endpoint verdict, especially for empty
    # or incomplete input. Never promote it into physical movement evidence.
    assert result['physical_movement_verified'] is False
    assert result['sample_freshness_verified'] is False


@pytest.mark.parametrize('phase', ['baseline', 'post'])
@pytest.mark.parametrize('cancel_at', ['before_read', 'during_read'])
def test_campaign_cancellation_retains_returned_bytes_without_another_read(
        tmp_path, phase, cancel_at):
    _, reader, clock = setup(tmp_path)
    start = clock[0]
    event = Event()
    calls = []
    if cancel_at == 'before_read':
        event.set()
    def read(size, timeout):
        calls.append(size)
        event.set()
        return b'partial-at-cancel'
    result = capture_campaign_window(reader.request, phase, read_once=read,
        cancellation=event, clock_ns=lambda: clock[0],
        command_completed_ns=start if phase == 'post' else None)
    assert result['status'] == 'CANCELLED'
    assert result['read_calls'] == len(calls) == (cancel_at == 'during_read')
    raw = b''.join(base64.b64decode(chunk) for chunk in result['raw']['base64_chunks'])
    assert raw == (b'partial-at-cancel' if calls else b'')
    assert result['physical_stop_verified'] is False
    with pytest.raises(ValueError):
        validate_campaign_capture(reader.request, result, phase=phase,
            command_completed_ns=start if phase == 'post' else None)


@pytest.mark.parametrize('phase,capacity', [('baseline', 16384), ('post', 49152)])
def test_campaign_capacity_retains_every_byte_and_cannot_pass(tmp_path, phase, capacity):
    _, reader, clock = setup(tmp_path)
    request = reader.request
    start = clock[0]
    calls = []
    def read(size, timeout):
        calls.append(size)
        return b'x' * size
    result = capture_campaign_window(request, phase, read_once=read,
        cancellation=Event(), clock_ns=lambda: clock[0],
        idle_wait=lambda seconds: clock.__setitem__(0, clock[0] + round(seconds * 1e9)),
        command_completed_ns=start if phase == 'post' else None)
    assert result['status'] == 'BYTE_CAPACITY_REACHED'
    raw = b''.join(base64.b64decode(chunk) for chunk in result['raw']['base64_chunks'])
    assert raw == b'x' * capacity
    assert sum(calls) == capacity
    assert result['read_calls'] == capacity // 256
    assert not result['physical_movement_verified']
    with pytest.raises(ValueError):
        validate_campaign_capture(request, result, phase=phase,
            command_completed_ns=start if phase == 'post' else None)


@pytest.mark.parametrize('phase', ['baseline', 'post'])
def test_campaign_late_completion_keeps_original_but_fails_validation(tmp_path, phase):
    _, reader, clock = setup(tmp_path)
    start = clock[0]
    duration_ns = (1 if phase == 'baseline' else 5) * 1_000_000_000
    def read(size, timeout):
        clock[0] += duration_ns + 1
        return b'late-partial-frame'
    result = capture_campaign_window(reader.request, phase, read_once=read,
        cancellation=Event(), clock_ns=lambda: clock[0],
        command_completed_ns=start if phase == 'post' else None)
    assert result['status'] == 'READ_COMPLETED_AFTER_WINDOW'
    assert result['read_calls'] == 1
    assert result['within_deadline_bytes'] == 0
    assert result['late_completion_bytes'] == len(b'late-partial-frame')
    assert b''.join(base64.b64decode(c) for c in result['raw']['base64_chunks']) == b'late-partial-frame'
    with pytest.raises(ValueError):
        validate_campaign_capture(reader.request, result, phase=phase,
            command_completed_ns=start if phase == 'post' else None)
