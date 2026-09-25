"""Validate clean retained captures before recomputing commissioning metrics.

Failure captures remain retained as originals; this validator does not repair
them or turn process/telemetry claims into independent physical evidence.
"""
import base64
import hashlib

from rocell.arm.telemetry_coverage import analyze_window_coverage, complete_frame_interval
from .first_motion_contract import FirstMotionRequest, canonical


def validate_clean_first_motion_capture(request,capture,*,phase,command_completed_ns=None):
    """Return verified original bytes, with bounded schema/coverage checks.

    Use only after bounded IPC JSON decoding. This is not a parser for arbitrary
    unbounded Python objects, nor an owned-process receipt authenticator.
    """
    if type(request) is not FirstMotionRequest:
        raise ValueError('Exact measured commissioning request required')
    return _validate_clean_capture(request, capture, phase=phase,
        command_completed_ns=command_completed_ns, body=request.to_dict(),
        schema='rocell.first_motion_capture_window.v1')


def _validate_clean_capture(request, capture, *, phase, command_completed_ns, body, schema,
                            early_end_guard_ns=None):
    """Common bounded original verification; typed wrappers select the domain."""
    fields={'schema','request_sha256','phase','status','errors','read_calls',
        'started_ns','window_deadline_ns','finished_ns','within_deadline_bytes',
        'late_completion_bytes','raw','read_windows','abnormal_completion',
        'untimed_completion','coverage','native_cleanup_owned_by_caller',
        'physical_movement_verified','sample_freshness_verified','physical_stop_verified'}
    if early_end_guard_ns is not None:
        if phase!='baseline' or type(early_end_guard_ns) is not int or early_end_guard_ns<=0:
            raise ValueError('Bounded baseline early-end guard required')
        fields=fields|{'observation_end_ns'}
    if (phase not in {'baseline','post'}
            or type(capture) is not dict
            or set(capture) not in (fields,fields|{'baseline_framing'})
            or capture['schema']!=schema
            or capture['request_sha256']!=request.request_sha256 or capture['phase']!=phase):
        raise ValueError('Exact commissioning capture/request association required')
    if (capture['status']!='WINDOW_COMPLETE' or capture['errors']!=[]
            or capture['abnormal_completion'] is not None or capture['untimed_completion'] is not None
            or capture['native_cleanup_owned_by_caller'] is not True
            or any(capture[k] is not False for k in ('physical_movement_verified',
                       'sample_freshness_verified','physical_stop_verified'))):
        raise ValueError('Clean diagnostic-only capture required')
    limits=body['limits']
    original=capture['raw']
    if type(original) is not dict or set(original)!={'bytes','sha256','base64_chunks'}:
        raise ValueError('Exact original-byte envelope required')
    maximum=limits[f'maximum_{phase}_bytes']
    chunks=original['base64_chunks']
    if (type(chunks) is not list or len(chunks)>(maximum+767)//768
            or any(type(c) is not str or len(c)>1024 for c in chunks)):
        raise ValueError('Capture chunk budget exceeded')
    raw=b''.join(base64.b64decode(c,validate=True) for c in chunks)
    expected_chunks=[base64.b64encode(raw[i:i+768]).decode('ascii') for i in range(0,len(raw),768)]
    if (type(original['bytes']) is not int or len(raw)!=original['bytes'] or len(raw)>maximum
            or original['sha256']!=hashlib.sha256(raw).hexdigest() or chunks!=expected_chunks):
        raise ValueError('Original bytes/digest/encoding mismatch')
    started,deadline,finished=(capture[k] for k in ('started_ns','window_deadline_ns','finished_ns'))
    if (any(type(t) is not int for t in (started,deadline,finished))
            or not body['issued_monotonic_ns']<=started<deadline<body['deadline_monotonic_ns']
            or deadline+2_000_000_000>body['deadline_monotonic_ns']):
        raise ValueError('Invalid capture time window')
    observation_end=deadline
    if early_end_guard_ns is None:
        if not deadline<=finished<body['deadline_monotonic_ns']:
            raise ValueError('Invalid capture time window')
    else:
        observation_end=capture['observation_end_ns']
        if (type(observation_end) is not int or not started<observation_end<=finished<=deadline
                or observation_end<deadline-early_end_guard_ns):
            raise ValueError('Invalid early observation end')
    duration=limits['maximum_baseline_ms' if phase=='baseline' else 'maximum_post_observation_ms']*1_000_000
    if phase=='post':
        if type(command_completed_ns) is not int or not body['issued_monotonic_ns']<=command_completed_ns<=started:
            raise ValueError('Original write completion required')
        expected_deadline=command_completed_ns+duration
    else:
        expected_deadline=started+duration
    if deadline!=expected_deadline:
        raise ValueError('Capture deadline changed')
    windows=capture['read_windows']
    if (type(windows) is not list or type(capture['read_calls']) is not int
            or not len(windows)==capture['read_calls']<=limits[f'maximum_{phase}_reads']
            or type(capture['within_deadline_bytes']) is not int or capture['within_deadline_bytes']!=len(raw)
            or type(capture['late_completion_bytes']) is not int or capture['late_completion_bytes']!=0):
        raise ValueError('Capture read/byte accounting mismatch')
    coverage=analyze_window_coverage(raw,windows,display_limit=0, maximum_bytes=max(65536,maximum))
    if any(not started<=row[2]<=row[3]<=observation_end for row in windows):
        raise ValueError('Read window outside capture')
    if canonical(coverage)!=canonical(capture['coverage']):
        raise ValueError('Retained coverage summary differs from original bytes')
    if 'baseline_framing' in capture:
        if phase!='baseline': raise ValueError('Baseline framing on wrong phase')
        _,_,framing=complete_frame_interval(raw,windows,maximum_bytes=max(65536,maximum))
        if canonical(framing)!=canonical(capture['baseline_framing']):
            raise ValueError('Baseline framing changed')
    return raw
