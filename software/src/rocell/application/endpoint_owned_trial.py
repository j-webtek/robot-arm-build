"""One endpoint trial on an already exclusively owned, admitted connection.

Trusted worker dependencies enforce native timeouts and handle ownership. This
module neither opens a port nor supplies a native writer, and cannot preempt a
blocked callback. Parent supervision remains required for physical deployment.
"""

import base64
from dataclasses import dataclass
import math
from threading import Event
import time

from rocell.arm.movement_analysis import WIRE_AXES
from rocell.arm.telemetry_coverage import iter_window_records, complete_frame_interval, analyze_window_coverage
from rocell.motion.characterization_plan import AXES
from rocell.safety.bench_endpoint import BenchEndpointPermit
from .endpoint_capture import capture_endpoint_window, analyze_endpoint_capture
from .endpoint_trial_contract import EndpointTrialRequest
from .endpoint_write_boundary import EndpointWriteBoundary, EndpointWriteContext


class _BaselineRefusal(ValueError):
    """Fixed internal diagnostic codes, safe to retain in wizard exports."""


@dataclass(frozen=True, slots=True)
class EndpointCleanupResult:
    """Worker-reported native resources, never a physical stop acknowledgment."""

    all_handles_closed: bool
    pending_io_count: int


def _baseline_context(request, capture, *, connection_id, presence_expires_ns):
    # This capture was just created by our collector, not accepted from JSON.
    if capture['status'] != 'WINDOW_COMPLETE' or capture['errors']:
        raise _BaselineRefusal('BASELINE_CAPTURE_NOT_CLEAN')
    raw = b''.join(base64.b64decode(c, validate=True) for c in capture['raw']['base64_chunks'])
    raw, windows, framing = complete_frame_interval(raw,capture['read_windows'])
    capture['baseline_frame_interval'] = framing
    if analyze_window_coverage(raw,windows,display_limit=0)['unprocessed_range'] is not None:
        raise _BaselineRefusal('BASELINE_HAS_UNFRAMED_SUFFIX')
    body = request.to_dict()
    trial = next(t for t in body['campaign']['trials'] if t['trial_id'] == body['trial_id'])
    start = tuple(trial['start'][axis] for axis in AXES)
    last = first_finish = None
    count = 0
    max_gap = round(trial['stop']['max_read_gap_s']*1e9)
    previous_finish = capture['started_ns']
    for record in iter_window_records(raw, windows):
        if record['kind'] != 'POSE_TELEMETRY':
            raise _BaselineRefusal('BASELINE_CONTAINS_INVALID_POSE')
        pose = tuple(record['fields'][axis] for axis in WIRE_AXES)
        if any(type(v) not in (int, float) or not math.isfinite(v) or abs(v)>1e6 for v in pose):
            raise _BaselineRefusal('BASELINE_NUMERIC_RANGE')
        begin, finish = record['host_acquisition_bounds_ns']
        if begin-previous_finish > max_gap:
            raise _BaselineRefusal('BASELINE_COVERAGE_GAP')
        if (math.dist(pose[:3], start[:3]) > trial['stop']['position_tolerance_mm']
                or max(abs(pose[i]-start[i]) for i in range(3,6)) > trial['stop']['angle_tolerance_rad']):
            raise _BaselineRefusal('BASELINE_START_MISMATCH')
        first_finish = finish if first_finish is None else first_finish
        previous_finish = finish
        last = (pose, begin, finish)
        count += 1
    if (count < 2 or last[1]-first_finish < min(100_000_000, round(trial['dwell_s']*1e9))
            or capture['finished_ns']-last[2] > max_gap):
        raise _BaselineRefusal('BASELINE_INSUFFICIENT_STABLE_COVERAGE')
    # Recency is host acquisition only. The permit's independent baseline review
    # must establish pose meaning/freshness; we never derive it from timestamps.
    return EndpointWriteContext(connection_id, body['usb_identity']['serial_number'],
        tuple(sorted(body['references'].items())), last[0], last[2], presence_expires_ns)


def run_owned_endpoint_trial(request, permit, *, connection_id, read_once,
                             write_once, close_once, presence_expiry_reader,
                             cancellation, basis, clock_ns=None):
    """Capture baseline -> one write -> endpoint capture -> unconditional cleanup.

    Called once by the owning worker, never directly with browser callbacks.
    close_once(timeout_ms) must drain/cancel pending I/O and report ownership.
    Uncertain writes retain post evidence but never qualify as successful trials.
    """
    clock_ns = time.monotonic_ns if clock_ns is None else clock_ns
    if (type(request) is not EndpointTrialRequest or type(permit) is not BenchEndpointPermit
            or type(cancellation) is not Event
            or basis not in {'SYNTHETIC_WIRE_REHEARSAL','RETAINED_PHYSICAL_CAPTURE'}
            or any(not callable(c) for c in (read_once,write_once,close_once,presence_expiry_reader,clock_ns))):
        raise ValueError('Exact bench request/permit and owned worker dependencies required')
    result = {'schema':'rocell.owned_endpoint_trial.v1', 'request_sha256':request.request_sha256,
              'basis':basis, 'status':'NOT_SENT', 'baseline':None, 'write':None,
              'post':None, 'analysis':None, 'cleanup':None, 'errors':[],
              'physical_stop_verified':False, 'physical_movement_verified':False,
              'replay_allowed':False}
    try:
        request.require_start_time(clock_ns())
        if cancellation.is_set():
            result['status'] = 'CANCELLED_BEFORE_WRITE'
        else:
            result['baseline'] = capture_endpoint_window(request, 'baseline',
                read_once=read_once, cancellation=cancellation, clock_ns=clock_ns)
            context = _baseline_context(request, result['baseline'], connection_id=connection_id,
                                        presence_expires_ns=presence_expiry_reader())
            boundary = EndpointWriteBoundary(request, permit, connection_id=connection_id, clock_ns=clock_ns)
            result['write'] = boundary.attempt(context_reader=lambda:context,
                                              write_once=write_once, cancellation=cancellation)
            write = result['write']
            result['status'] = write['status']
            if write['write_attempted']:
                result['post'] = capture_endpoint_window(request, 'post', read_once=read_once,
                    cancellation=cancellation, clock_ns=clock_ns,
                    command_completed_ns=write['write_finished_ns'])
                result['analysis'] = analyze_endpoint_capture(request, result['post'],
                    command_completed_ns=write['write_finished_ns'], basis=basis)
                if not write['write_completion_uncertain']:
                    result['status'] = result['analysis']['status']
    except Exception as error:
        # Do not leak callback messages or replace retained evidence on failure.
        result['errors'].append(str(error) if type(error) is _BaselineRefusal else type(error).__name__)
        result['status'] = ('TRIAL_FAILED_AFTER_WRITE' if result['write']
                            and result['write']['write_attempted'] else 'HELD_BEFORE_WRITE')
    finally:
        permit.revoke()
        started = None
        try:
            started = clock_ns()
        except Exception as error:
            # A failed diagnostic clock must never skip native cleanup.
            result['errors'].append(type(error).__name__)
        try:
            cleanup = close_once(2000)
            finished = clock_ns()
            timed = (type(started) is int and type(finished) is int
                     and 0 < started <= finished < 2**63)
            elapsed = finished-started if timed else None
            valid = (type(cleanup) is EndpointCleanupResult
                     and type(cleanup.all_handles_closed) is bool
                     and type(cleanup.pending_io_count) is int
                     and cleanup.pending_io_count >= 0)
            clean = (valid and cleanup.all_handles_closed and cleanup.pending_io_count == 0
                     and timed and elapsed <= 2_000_000_000
                     and finished <= request.to_dict()['deadline_monotonic_ns'])
            result['cleanup'] = {'status':'HANDLES_CLOSED' if clean else 'CLEANUP_UNCERTAIN',
                                 'elapsed_ns':elapsed, 'physical_stop_verified':False,
                                 'all_handles_closed':cleanup.all_handles_closed if valid else None,
                                 'pending_io_count':cleanup.pending_io_count if valid else None}
        except Exception as error:
            clean = False
            result['errors'].append(type(error).__name__)
            result['cleanup'] = {'status':'CLEANUP_UNCERTAIN', 'physical_stop_verified':False}
        if not clean:
            result['status_before_cleanup_failure'] = result['status']
            result['status'] = 'CLEANUP_UNCERTAIN'
    return result
