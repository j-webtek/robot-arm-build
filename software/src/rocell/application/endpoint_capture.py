"""Bounded read windows for an already-owned endpoint connection.

No open, write, purge, retry or close operations exist here. The owning executor
must supply a timeout-enforcing reader and retain/close its native handles even
when this collector fails. Python cannot preempt an arbitrary blocking callback.
"""

import base64
import hashlib
from threading import Event
import time

from rocell.arm.telemetry_coverage import analyze_window_coverage
from rocell.arm.movement_analysis import analyze_endpoint_trial
from rocell.motion.characterization_plan import freeze_campaign
from .endpoint_trial_contract import EndpointTrialRequest


def capture_endpoint_window(request, phase, *, read_once, cancellation,
                            clock_ns=time.monotonic_ns, idle_wait=None,
                            command_completed_ns=None):
    """Read at most one baseline or post window; retain late completions too.

    Reader signature: read_once(maximum_bytes, timeout_ms) -> exact bytes.
    Timestamps bracket each host call, never assign device generation times.
    Limits and errors do not imply that motion already accepted has stopped.
    """
    if (type(request) is not EndpointTrialRequest or phase not in {'baseline','post'}
            or type(cancellation) is not Event or not callable(read_once) or not callable(clock_ns)):
        raise ValueError('Exact request, phase, event and owned reader required')
    if idle_wait is not None and not callable(idle_wait):
        raise ValueError('Invalid idle wait dependency')
    body = request.to_dict()
    limits = body['limits']
    window_ms = limits['maximum_baseline_ms'] if phase == 'baseline' else limits['maximum_post_observation_ms']
    if phase == 'post':
        trial = next(t for t in body['campaign']['trials'] if t['trial_id'] == body['trial_id'])
        window_ms = min(window_ms, trial['timeout_s']*1000)
    return _capture_owned_window(request, phase, read_once=read_once,
        cancellation=cancellation, clock_ns=clock_ns, idle_wait=idle_wait,
        command_completed_ns=command_completed_ns, window_ms=window_ms,
        schema='rocell.endpoint_capture_window.v1')


def _capture_owned_window(request, phase, *, read_once, cancellation, clock_ns,
                          idle_wait, command_completed_ns, window_ms, schema, runtime_body=None,
                          read_end_guard_ms=0, minimum_read_interval_ms=0, finish_at_read_guard=False):
    """Shared collector; only typed wrappers select limits, duration and schema.

    This private helper grants no admission and never opens or writes a device.
    Keeping the read loop shared preserves late-byte retention and timeout/error
    behavior without converting commissioning requests into endpoint requests.
    """
    if type(finish_at_read_guard) is not bool or (finish_at_read_guard and (phase!='baseline' or read_end_guard_ms<=0)):
        raise ValueError('Early completion requires a guarded baseline capture')
    body = request.to_dict() if runtime_body is None else runtime_body
    limits = body['limits']
    maximum_bytes = limits[f'maximum_{phase}_bytes']
    maximum_reads = limits[f'maximum_{phase}_reads']
    previous_time = 0

    def clock():
        nonlocal previous_time
        value = clock_ns()
        if type(value) is not int or not 0 < value < 2**63 or value < previous_time:
            raise ValueError('INVALID_OR_BACKWARDS_CAPTURE_CLOCK')
        previous_time = value
        return value

    started = clock()
    deadline = started + round(window_ms*1_000_000)
    if phase == 'post':
        if (type(command_completed_ns) is not int
                or not body['issued_monotonic_ns'] <= command_completed_ns <= started):
            raise ValueError('Post capture requires the actual command-completion time')
        # The trial timeout starts at command completion, not at a delayed
        # collector start. Never silently extend the observation contract.
        deadline = min(deadline, command_completed_ns + round(window_ms*1_000_000))
        if started >= deadline:
            raise ValueError('Post capture started after the trial deadline')
    if started < body['issued_monotonic_ns'] or deadline+2_000_000_000 > body['deadline_monotonic_ns']:
        raise ValueError('Capture cannot fit before reserved cleanup deadline')
    raw, windows, errors = bytearray(), [], []
    calls, within_deadline_bytes = 0, 0
    next_read_ns = started
    abnormal = None
    untimed_completion = None
    status = 'WINDOW_COMPLETE'
    observation_end = deadline
    try:
        while True:
            now = clock()
            if cancellation.is_set():
                status = 'CANCELLED'
                break
            if now >= deadline:
                break
            # Observational capture reserves a short tail for host scheduling.
            # Do not launch a final read that is almost certain to straddle the
            # window. Keep the original deadline and timestamps; late bytes
            # from any read still fail below and are retained for diagnosis.
            if read_end_guard_ms and deadline-now <= (read_end_guard_ms+25)*1_000_000:
                if finish_at_read_guard:
                    # Record actual completion without pretending we observed
                    # the idle tail. Keep the original maximum deadline intact.
                    observation_end=now
                    break
                wait = cancellation.wait if idle_wait is None else idle_wait
                wait(min(.01, max(0, (deadline-now)/1e9)))
                continue
            # USB can complete many short reads immediately. Pace admission,
            # not timestamps or device feedback, so fragmentation cannot burn
            # the observational read budget before its fixed window ends.
            # Bytes stay in the driver until the next owned read; no purge,
            # fabricated samples, enlarged byte budget or deadline extension.
            if now < next_read_ns:
                wait = cancellation.wait if idle_wait is None else idle_wait
                wait(min(.01, (min(next_read_ns, deadline)-now)/1e9))
                continue
            if len(raw) == maximum_bytes:
                status = 'BYTE_CAPACITY_REACHED'
                break
            if calls == maximum_reads:
                status = 'READ_CALL_LIMIT_REACHED'
                break
            size = min(256, maximum_bytes-len(raw))
            timeout_ms = min(100, max(1,(deadline-now)//1_000_000-read_end_guard_ms))
            begin = clock()
            next_read_ns = begin + minimum_read_interval_ms*1_000_000
            calls += 1
            block = read_once(size, timeout_ms)
            try:
                finish = clock()
            except Exception as error:
                # Bytes returned before a clock failure still belong in the
                # diagnostic evidence, but must not receive invented timing.
                if type(block) is bytes and len(block) <= size:
                    untimed_completion = {'bytes':len(block),
                        'sha256':hashlib.sha256(block).hexdigest(),
                        'base64':base64.b64encode(block).decode('ascii')}
                errors.append(type(error).__name__)
                status = 'CAPTURE_CLOCK_FAILED'
                break
            if type(block) is not bytes or len(block) > size:
                # A broken dependency must not expand our byte/work budget or
                # produce fake valid read windows. Preserve a bounded prefix.
                abnormal = {'kind':type(block).__name__,
                            'returned_bytes':len(block) if type(block) is bytes else None,
                            'retained_prefix_base64':base64.b64encode(block[:256]).decode('ascii') if type(block) is bytes else None,
                            'complete_original_retained':False}
                status = 'READER_CONTRACT_VIOLATION'
                break
            offset = len(raw)
            raw.extend(block)
            windows.append([offset,len(raw),begin,finish])
            if finish <= deadline:
                within_deadline_bytes = len(raw)
            else:
                status = 'READ_COMPLETED_AFTER_WINDOW'
                break
            if finish-begin > timeout_ms*1_000_000:
                status = 'READER_TIMEOUT_BOUND_EXCEEDED'
                break
            if not block:
                wait = cancellation.wait if idle_wait is None else idle_wait
                wait(min(.01,max(0,(deadline-finish)/1e9)))
    except Exception as error:
        status = 'CAPTURE_FAILED'
        errors.append(type(error).__name__)
    # Clock failure must not erase already retained originals or read windows.
    try:
        finished = clock()
    except Exception as error:
        finished = previous_time
        errors.append(type(error).__name__)
        status = 'CAPTURE_FAILED'
    original = bytes(raw)
    result = {'schema':schema,'request_sha256':request.request_sha256,
            'phase':phase,'status':status,'errors':errors,'read_calls':calls,
            'started_ns':started,'window_deadline_ns':deadline,'finished_ns':finished,
            'within_deadline_bytes':within_deadline_bytes,
            'late_completion_bytes':len(raw)-within_deadline_bytes,
            'raw':{'bytes':len(original),'sha256':hashlib.sha256(original).hexdigest(),
                   'base64_chunks':[base64.b64encode(original[i:i+768]).decode('ascii') for i in range(0,len(original),768)]},
            'read_windows':windows,'abnormal_completion':abnormal,'untimed_completion':untimed_completion,
            'coverage':analyze_window_coverage(original,windows,display_limit=0, maximum_bytes=max(65536,maximum_bytes)),
            'native_cleanup_owned_by_caller':True,'physical_movement_verified':False,
            'sample_freshness_verified':False,'physical_stop_verified':False}
    if finish_at_read_guard:
        result['observation_end_ns']=observation_end
    return result


def analyze_endpoint_capture(request, capture, *, command_completed_ns, basis):
    """Rebuild endpoint metrics, withholding qualification on any capture fault."""
    if (type(request) is not EndpointTrialRequest or type(capture) is not dict
            or capture.get('schema') != 'rocell.endpoint_capture_window.v1'
            or capture.get('request_sha256') != request.request_sha256
            or capture.get('phase') != 'post'):
        raise ValueError('Exact post-capture/request association required')
    original = capture.get('raw')
    if type(original) is not dict or type(original.get('base64_chunks')) is not list:
        raise ValueError('Original capture chunks required')
    chunks = original['base64_chunks']
    if len(chunks) > 86 or any(type(c) is not str or len(c) > 1024 for c in chunks):
        raise ValueError('Original capture chunk budget exceeded')
    raw = b''.join(base64.b64decode(c,validate=True) for c in chunks)
    if (type(original.get('bytes')) is not int or len(raw) != original['bytes'] or len(raw)>65536
            or hashlib.sha256(raw).hexdigest() != original.get('sha256')):
        raise ValueError('Original capture digest/size mismatch')
    body = request.to_dict()
    if (type(command_completed_ns) is not int or type(capture.get('started_ns')) is not int
            or not body['issued_monotonic_ns'] <= command_completed_ns <= capture['started_ns']):
        raise ValueError('Invalid command/post-capture order')
    result = analyze_endpoint_trial(freeze_campaign(body['campaign']), body['trial_id'],raw,
        capture['read_windows'],command_completed_ns=command_completed_ns,
        observation_end_ns=capture['finished_ns'],basis=basis)
    result['request_sha256'] = request.request_sha256
    result['capture_status'] = capture.get('status')
    if (capture.get('status') != 'WINDOW_COMPLETE' or capture.get('errors') != []
            or capture.get('abnormal_completion') is not None or capture.get('untimed_completion') is not None):
        result['status'] = 'INSUFFICIENT_ENDPOINT_EVIDENCE'
        result['host_endpoint_dwell_entry_bounds_ns'] = None
        result['issues'] = sorted(set(result['issues']) | {'CAPTURE_NOT_CLEANLY_COMPLETED'})
    return result
