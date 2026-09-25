"""Typed observational wrapper for the shared bounded raw-byte collector."""
from threading import Event
import time

from rocell.safety.observational_review_authority import ObservationalIntent
from .endpoint_capture import _capture_owned_window
from .first_motion_capture_validation import _validate_clean_capture

SCHEMA = 'rocell.observational_capture_window.v1'


def capture_observational_window(request, phase, *, read_once, cancellation,
        clock_ns=time.monotonic_ns, idle_wait=None, command_completed_ns=None):
    if (type(request) is not ObservationalIntent or phase not in ('baseline', 'post')
            or type(cancellation) is not Event or not callable(read_once) or not callable(clock_ns)
            or (idle_wait is not None and not callable(idle_wait))):
        raise ValueError('Exact observational collector dependencies required')
    return _capture_owned_window(request, phase, read_once=read_once,
        cancellation=cancellation, clock_ns=clock_ns, idle_wait=idle_wait,
        command_completed_ns=command_completed_ns, window_ms=1000 if phase == 'baseline' else 5000,
        schema=SCHEMA, runtime_body=request.runtime_body(), read_end_guard_ms=25,
        minimum_read_interval_ms=10)


def validate_clean_observational_capture(request, capture, *, phase, command_completed_ns=None):
    if type(request) is not ObservationalIntent:
        raise ValueError('Exact observational capture request required')
    return _validate_clean_capture(request, capture, phase=phase,
        command_completed_ns=command_completed_ns, body=request.runtime_body(), schema=SCHEMA)
