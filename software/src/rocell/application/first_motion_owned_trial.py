"""Commissioning sequence on an already-owned connection, not a live launcher.

Native composition must enforce timeouts, handle ownership and the permit's
dispatch claim. Python callbacks cannot preempt a blocked driver. The owning
supervisor must also retain results if this process becomes unresponsive.
"""
from dataclasses import dataclass
import math
from threading import Event
import time

from rocell.arm.first_motion_analysis import _window, TOLERANCE_RAD, analyze_first_motion
from rocell.arm.protocol import encode_line
from rocell.safety.first_motion_admission import FirstMotionPermit
from .first_motion_contract import FirstMotionRequest
from .first_motion_capture import capture_first_motion_window
from .first_motion_capture_validation import validate_clean_first_motion_capture


@dataclass(frozen=True, slots=True)
class FirstMotionCleanupResult:
    all_handles_closed: bool
    pending_io_count: int


def _baseline(request, capture):
    if capture['status'] != 'WINDOW_COMPLETE' or capture['errors']:
        raise ValueError('Baseline capture did not complete cleanly')
    raw = validate_clean_first_motion_capture(request,capture,phase='baseline')
    rows, issues, framing = _window(raw,capture['read_windows'],
                                   capture['started_ns'],capture['finished_ns'])
    capture['baseline_framing'] = framing
    if issues or rows[-1][0]-rows[0][1] < 100_000_000:
        raise ValueError('Insufficient baseline coverage')
    start = rows[-1][2]
    low, high = map(math.radians,request.to_dict()['independent_start_interval_deg'])
    if (any(not low <= row[2][3] <= high for row in rows)
            or any(abs(row[2][i]-start[i]) > TOLERANCE_RAD for row in rows for i in range(6))):
        raise ValueError('Unstable or inconsistent reported baseline')
    return rows[-1][1]  # Host acquisition recency, never device freshness.


def run_owned_first_motion_trial(request, permit, *, connection_id, read_once,
                                  write_once, close_once, cancellation, basis,
                                  clock_ns=time.monotonic_ns):
    """Baseline -> consume -> one write -> post capture -> unconditional cleanup.

    Dependencies are trusted worker internals, never browser-supplied callbacks.
    write_once must use the matching admitted native facade on this owned port.
    No automatic return, retry, torque change or physical-stop claim is made.
    """
    if (type(request) is not FirstMotionRequest or type(permit) is not FirstMotionPermit
            or type(cancellation) is not Event
            or basis not in {'SYNTHETIC_WIRE_REHEARSAL','RETAINED_PHYSICAL_CAPTURE'}
            or any(not callable(c) for c in (read_once,write_once,close_once,clock_ns))):
        raise ValueError('Exact commissioning request/permit and owned dependencies required')
    result = dict(schema='rocell.owned_first_motion_trial.v1',basis=basis,
        request_sha256=request.request_sha256,status='NOT_SENT',baseline=None,post=None,
        write=None,analysis=None,cleanup=None,errors=[],physical_movement_verified=False,
        physical_stop_verified=False,campaign_advance_allowed=False,replay_allowed=False)
    last = 0
    def now():
        nonlocal last
        value = clock_ns()
        if type(value) is not int or not 0 < value < 2**63 or value < last:
            raise ValueError('Invalid commissioning clock')
        last = value
        return value
    try:
        request.require_start_time(now())
        if cancellation.is_set():
            result['status'] = 'CANCELLED_BEFORE_WRITE'
            return result
        result['baseline'] = capture_first_motion_window(request,'baseline',read_once=read_once,
            cancellation=cancellation,clock_ns=now)
        acquired = _baseline(request,result['baseline'])
        if cancellation.is_set() or not permit.consume_for_write(request,connection_id,
                                                                  baseline_acquired_ns=acquired):
            raise ValueError('Cancelled or commissioning permit refused')
        if cancellation.is_set():
            raise ValueError('Cancelled after consumption')
        payload = encode_line(request.to_dict()['command'])
        started = now()
        if started-acquired > 100_000_000 or started+8_000_000_000 > request.to_dict()['deadline_monotonic_ns']:
            raise ValueError('Write acquisition/budget expired')
        write = result['write'] = dict(write_attempted=True,write_started_ns=started,
            write_finished_ns=None,confirmed_write_bytes=0,write_completion_uncertain=True)
        try:
            count = write_once(payload)
            if type(count) is int and 0 <= count <= len(payload):
                write['confirmed_write_bytes'] = count
            write['write_finished_ns'] = now()
            write['write_completion_uncertain'] = (type(count) is not int or count != len(payload)
                or write['write_finished_ns']-started > 1_000_000_000)
        except Exception as error:
            result['errors'].append(type(error).__name__)
            write['write_finished_ns'] = now()
        # Even uncertain submission may have moved hardware; preserve post data
        # when its time budget permits. Never resubmit the remaining bytes.
        result['status'] = 'WRITE_UNCERTAIN_NO_RETRY' if write['write_completion_uncertain'] else 'WRITE_COMPLETED_NOT_MOVEMENT_VERIFIED'
        result['post'] = capture_first_motion_window(request,'post',read_once=read_once,
            cancellation=cancellation,clock_ns=now,command_completed_ns=write['write_finished_ns'])
        post, baseline = result['post'], result['baseline']
        if post['status'] == 'WINDOW_COMPLETE' and not post['errors']:
            baseline_raw = validate_clean_first_motion_capture(request,baseline,phase='baseline')
            post_raw = validate_clean_first_motion_capture(request,post,phase='post',
                command_completed_ns=write['write_finished_ns'])
            result['analysis'] = analyze_first_motion(request,baseline_raw,baseline['read_windows'],
                post_raw,post['read_windows'],baseline_started_ns=baseline['started_ns'],
                baseline_finished_ns=baseline['finished_ns'],write_started_ns=started,
                write_finished_ns=write['write_finished_ns'],observation_end_ns=post['finished_ns'],basis=basis)
            if not write['write_completion_uncertain']:
                result['status'] = result['analysis']['status']
        elif not write['write_completion_uncertain']:
            result['status'] = 'POST_CAPTURE_INCOMPLETE'
    except Exception as error:
        result['errors'].append(type(error).__name__)  # Never export arbitrary device error text.
        result['status'] = 'TRIAL_FAILED_AFTER_WRITE' if result['write'] else 'HELD_BEFORE_WRITE'
    finally:
        permit.revoke()
        started = None
        try:
            started = now()
        except Exception as error:
            result['errors'].append(type(error).__name__)
        try:
            cleanup = close_once(2000)  # Must run even if the diagnostic clock failed.
            finished = now()
            valid = (type(cleanup) is FirstMotionCleanupResult
                and type(cleanup.all_handles_closed) is bool
                and type(cleanup.pending_io_count) is int and cleanup.pending_io_count >= 0)
            clean = (valid and cleanup.all_handles_closed and cleanup.pending_io_count == 0
                and started is not None and 0 <= finished-started <= 2_000_000_000
                and finished <= request.to_dict()['deadline_monotonic_ns'])
            result['cleanup'] = dict(status='HANDLES_CLOSED' if clean else 'CLEANUP_UNCERTAIN',
                started_ns=started,finished_ns=finished,
                all_handles_closed=cleanup.all_handles_closed if valid else None,
                pending_io_count=cleanup.pending_io_count if valid else None)
        except Exception as error:
            clean = False
            result['errors'].append(type(error).__name__)
            result['cleanup'] = dict(status='CLEANUP_UNCERTAIN')
        if not clean:
            result['status_before_cleanup_failure'] = result['status']
            result['status'] = 'CLEANUP_UNCERTAIN'
    return result
