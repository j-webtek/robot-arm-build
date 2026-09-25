"""One observational trial on an already-open, exclusively owned connection.

The native worker must enforce blocking-I/O/process deadlines. Callbacks here
are trusted internals, not browser inputs. Closing USB is not a physical stop.
"""
from threading import Event
import time

from rocell.safety.observational_review_authority import ObservationalIntent
from rocell.safety.observational_admission import ObservationalPermit
from .endpoint_owned_trial import EndpointCleanupResult
from .observational_capture import capture_observational_window, validate_clean_observational_capture


def run_owned_observational_trial(request, permit, *, connection_id, port_name,
        read_once, write_once, close_once, cancellation, basis, clock_ns=time.monotonic_ns,
        idle_wait=None):
    if (type(request) is not ObservationalIntent or type(permit) is not ObservationalPermit
            or type(cancellation) is not Event
            or basis not in ('SYNTHETIC_WIRE_REHEARSAL', 'RETAINED_PHYSICAL_CAPTURE')
            or any(not callable(fn) for fn in (read_once, write_once, close_once, clock_ns))):
        raise ValueError('Exact observational trial dependencies required')
    result = dict(schema='rocell.owned_observational_trial.v1', basis=basis,
        request_sha256=request.request_sha256, status='NOT_SENT', baseline=None, post=None,
        selection=None, write=None, cleanup=None, errors=[], physical_movement_verified=False,
        physical_stop_verified=False, campaign_advance_allowed=False, replay_allowed=False)
    last = 0
    def now():
        nonlocal last
        current = clock_ns()
        if type(current) is not int or not 0 < current < 2**63 or current < last:
            raise ValueError('Invalid observational clock')
        last = current
        return current
    try:
        request.require_start_time(now())
        if cancellation.is_set():
            result['status'] = 'CANCELLED_BEFORE_WRITE'
            return result
        baseline = result['baseline'] = capture_observational_window(request, 'baseline',
            read_once=read_once, cancellation=cancellation, clock_ns=now, idle_wait=idle_wait)
        raw = validate_clean_observational_capture(request, baseline, phase='baseline')
        result['selection'] = permit.bind_owned_baseline(request, connection_id, port_name,
            raw, baseline['read_windows'], started_ns=baseline['started_ns'], finished_ns=baseline['finished_ns'])
        if cancellation.is_set():
            result['status'] = 'CANCELLED_BEFORE_WRITE'
            return result
        payload = permit.selected_payload()
        started = now()
        write = result['write'] = dict(write_started_ns=started, write_finished_ns=None,
            write_attempted=True, confirmed_write_bytes=0, write_completion_uncertain=True)
        try:
            # The native facade claims the one-use dispatch immediately before
            # submission. An exception or short write must never be retried.
            count = write_once(payload)
            finished = now()
            write['write_finished_ns'] = finished
            if type(count) is int and 0 <= count <= len(payload):
                write['confirmed_write_bytes'] = count
            write['write_completion_uncertain'] = (type(count) is not int
                or count != len(payload) or finished-started > 1_000_000_000)
        except Exception as error:
            result['errors'].append(type(error).__name__)
            write['write_finished_ns'] = now()
        result['status'] = 'WRITE_UNCERTAIN_NO_RETRY' if write['write_completion_uncertain'] else 'AWAITING_OPERATOR_OBSERVATION'
        # Retain post data even after uncertain submission: hardware may have
        # accepted the command. This does not mean another submission is allowed.
        post = result['post'] = capture_observational_window(request, 'post',
            read_once=read_once, cancellation=cancellation, clock_ns=now, idle_wait=idle_wait,
            command_completed_ns=write['write_finished_ns'])
        if post['status'] == 'WINDOW_COMPLETE':
            validate_clean_observational_capture(request, post, phase='post',
                command_completed_ns=write['write_finished_ns'])
        elif not write['write_completion_uncertain']:
            result['status'] = 'POST_CAPTURE_INCOMPLETE'
    except Exception as error:
        result['errors'].append(type(error).__name__)
        result['status'] = 'TRIAL_FAILED_AFTER_WRITE' if result['write'] else 'HELD_BEFORE_WRITE'
    finally:
        permit.revoke()
        started = None
        try:
            started = now()
        except Exception as error:
            result['errors'].append(type(error).__name__)
        try:
            cleanup = close_once(2000)
            finished = now()
            valid = (type(cleanup) is EndpointCleanupResult
                and type(cleanup.all_handles_closed) is bool
                and type(cleanup.pending_io_count) is int and cleanup.pending_io_count >= 0)
            clean = (valid and cleanup.all_handles_closed and cleanup.pending_io_count == 0
                and started is not None and finished-started <= 2_000_000_000
                and finished <= request.to_dict()['deadline_ns'])
            result['cleanup'] = dict(status='HANDLES_CLOSED' if clean else 'CLEANUP_UNCERTAIN',
                started_ns=started, finished_ns=finished,
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
