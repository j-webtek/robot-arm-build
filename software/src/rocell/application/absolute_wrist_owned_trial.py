"""Integrated one-command absolute trial on an owned synthetic connection.

Native provenance is deliberately rejected pending typed facade/worker review.
Callbacks are trusted test/host internals, never browser-supplied code. Cleanup
closes ownership; it does not establish that an already-issued servo goal stopped.
"""
import base64
from threading import Event
import time

from rocell.safety.absolute_wrist_review_authority import AbsoluteWristIntent
from .absolute_wrist_capture import capture_absolute_wrist_window, validate_absolute_wrist_capture
from .absolute_wrist_command_binding import AbsoluteWristCommandBinding
from .absolute_wrist_result_review import review_absolute_wrist_result
from .endpoint_owned_trial import EndpointCleanupResult
from .first_motion_contract import canonical


def run_owned_absolute_wrist_trial(request, binding, *, read_once, write_once,
        close_once, cancellation, basis, clock_ns=time.monotonic_ns, idle_wait=None):
    if (type(request) is not AbsoluteWristIntent or type(binding) is not AbsoluteWristCommandBinding
            or binding._request != request or type(cancellation) is not Event
            or basis != 'SYNTHETIC_WIRE_REHEARSAL'
            or any(not callable(fn) for fn in (read_once, write_once, close_once, clock_ns))
            or (idle_wait is not None and not callable(idle_wait))):
        raise ValueError('Exact owned synthetic absolute-trial dependencies required')
    return _run_absolute_wrist_trial(request, binding, read_once=read_once, write_once=write_once,
        close_once=close_once, cancellation=cancellation, basis=basis, clock_ns=clock_ns,
        idle_wait=idle_wait)


def _run_absolute_wrist_trial(request, binding, *, read_once, write_once, close_once,
        cancellation, basis, clock_ns, idle_wait):
    """Shared internals; only exact synthetic/native composition may call this.

    The native adapter supplies selected bytes but consumes at the actual native
    submission boundary. The synthetic latch consumes before its fake write.
    """
    trial = dict(schema='rocell.absolute_wrist_trial.v1', request_sha256=request.request_sha256,
                 basis=basis, baseline=None, post=None, write=None, cleanup=None)
    result = dict(schema='rocell.owned_absolute_wrist_trial.v1', status='NOT_SENT',
        trial=trial, review=None, errors=[], motion_authorized=False,
        physical_movement_verified=False, physical_stop_verified=False,
        campaign_advance_allowed=False, replay_allowed=False)
    last = 0
    def now():
        nonlocal last
        value = clock_ns()
        if type(value) is not int or not 0 < value < 2**63 or value < last:
            raise ValueError('Invalid absolute-trial clock')
        last = value
        return value
    try:
        request.require_start_time(now())
        if cancellation.is_set():
            result['status'] = 'CANCELLED_BEFORE_WRITE'
        else:
            baseline = trial['baseline'] = capture_absolute_wrist_window(request, 'baseline',
                read_once=read_once, cancellation=cancellation, clock_ns=now, idle_wait=idle_wait)
            raw = validate_absolute_wrist_capture(request, baseline, phase='baseline')
            binding.bind_baseline(raw, baseline['read_windows'],
                started_ns=baseline['started_ns'], finished_ns=baseline['finished_ns'])
            if cancellation.is_set():
                result['status'] = 'CANCELLED_BEFORE_WRITE'
            else:
                payload = binding.consume_command()
                # A cancellation here still burns selection; it cannot be replayed.
                if cancellation.is_set():
                    result['status'] = 'CANCELLED_BEFORE_WRITE'
                else:
                    write = trial['write'] = dict(payload_base64=base64.b64encode(payload).decode('ascii'),
                        started_ns=now(), finished_ns=None, attempted=True,
                        confirmed_bytes=0, completion_uncertain=True)
                    try:
                        count = write_once(payload)
                        write['finished_ns'] = now()
                        if type(count) is int and 0 <= count <= len(payload):
                            write['confirmed_bytes'] = count
                        write['completion_uncertain'] = (type(count) is not int or count != len(payload)
                            or write['finished_ns'] - write['started_ns'] > 1_000_000_000)
                    except Exception as exc:
                        result['errors'].append(type(exc).__name__)
                        write['finished_ns'] = now()
                    result['status'] = 'WRITE_UNCERTAIN_NO_RETRY' if write['completion_uncertain'] else 'CAPTURED'
                    # A write exception may still have affected the device: retain
                    # post bytes, never resend or append a return/stop command.
                    trial['post'] = capture_absolute_wrist_window(request, 'post', read_once=read_once,
                        cancellation=cancellation, clock_ns=now, idle_wait=idle_wait,
                        command_completed_ns=write['finished_ns'])
    except Exception as exc:
        result['errors'].append(type(exc).__name__)
        result['status'] = 'FAILED_AFTER_WRITE' if trial['write'] else 'HELD_BEFORE_WRITE'
    finally:
        binding.revoke()
        started = None
        try:
            started = now()
        except Exception as exc:
            result['errors'].append(type(exc).__name__)
        try:
            cleanup = close_once(2000)  # Attempt even when the clock is broken.
            finished = now()
            if (type(cleanup) is not EndpointCleanupResult or type(cleanup.all_handles_closed) is not bool
                    or type(cleanup.pending_io_count) is not int or cleanup.pending_io_count < 0):
                raise ValueError('Invalid cleanup receipt')
            trial['cleanup'] = dict(started_ns=started, finished_ns=finished,
                all_handles_closed=cleanup.all_handles_closed, pending_io_count=cleanup.pending_io_count)
            if (not cleanup.all_handles_closed or cleanup.pending_io_count != 0 or started is None
                    or finished - started > 2_000_000_000 or finished > request.to_dict()['deadline_ns']):
                result['status'] = 'CLEANUP_UNCERTAIN'
        except Exception as exc:
            result['errors'].append(type(exc).__name__)
            result['status'] = 'CLEANUP_UNCERTAIN'
    if trial['write'] is not None and trial['post'] is not None and trial['cleanup'] is not None:
        try:
            result['review'] = review_absolute_wrist_result(request, canonical(trial), expected_basis=basis)
            endpoint = result['review']['endpoint']['status']
            result['status'] = 'REPORTED_SETTLED' if endpoint == 'REPORTED_SETTLED' else 'HELD_' + endpoint
        except Exception as exc:
            result['errors'].append(type(exc).__name__)
            result['status'] = 'RESULT_NOT_RECONSTRUCTABLE'
    return result
