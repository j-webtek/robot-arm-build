"""Exact-type absolute diagnostic wrapper for shared capture/validation."""
from threading import Event
import time

from rocell.safety.absolute_wrist_review_authority import AbsoluteWristIntent
from .endpoint_capture import _capture_owned_window
from .first_motion_capture_validation import _validate_clean_capture

SCHEMA = 'rocell.absolute_wrist_capture.v1'


def capture_absolute_wrist_window(request, phase, *, read_once, cancellation,
        clock_ns=time.monotonic_ns, idle_wait=None, command_completed_ns=None):
    if (type(request) is not AbsoluteWristIntent or phase not in ('baseline', 'post')
            or type(cancellation) is not Event or not callable(read_once) or not callable(clock_ns)
            or (idle_wait is not None and not callable(idle_wait))):
        raise ValueError('Exact absolute diagnostic capture dependencies required')
    return _capture_owned_window(request, phase, read_once=read_once,
        cancellation=cancellation, clock_ns=clock_ns, idle_wait=idle_wait,
        command_completed_ns=command_completed_ns, window_ms=1000 if phase == 'baseline' else 5000,
        schema=SCHEMA, runtime_body=request.runtime_body(), read_end_guard_ms=25,
        minimum_read_interval_ms=10)


def validate_absolute_wrist_capture(request, capture, *, phase, command_completed_ns=None):
    if type(request) is not AbsoluteWristIntent:
        raise ValueError('Exact absolute diagnostic request required')
    return _validate_clean_capture(request, capture, phase=phase,
        command_completed_ns=command_completed_ns, body=request.runtime_body(), schema=SCHEMA)
