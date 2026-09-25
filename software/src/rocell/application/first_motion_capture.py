"""Separate typed commissioning collector on an already-owned connection.

No device open, command submission or permission is provided by this module.
The worker must enforce native deadlines and unconditional cleanup externally.
"""
from threading import Event
import time

from .first_motion_contract import FirstMotionRequest
from .endpoint_capture import _capture_owned_window


def capture_first_motion_window(request, phase, *, read_once, cancellation,
                                clock_ns=time.monotonic_ns, idle_wait=None,
                                command_completed_ns=None):
    """Retain one fixed 1-second baseline or 5-second post-write window."""
    if (type(request) is not FirstMotionRequest or phase not in {'baseline','post'}
            or type(cancellation) is not Event or not callable(read_once)
            or not callable(clock_ns) or (idle_wait is not None and not callable(idle_wait))):
        raise ValueError('Exact commissioning request and owned reader required')
    limits = request.to_dict()['limits']
    duration = limits['maximum_baseline_ms' if phase=='baseline' else 'maximum_post_observation_ms']
    return _capture_owned_window(request, phase, read_once=read_once,
        cancellation=cancellation, clock_ns=clock_ns, idle_wait=idle_wait,
        command_completed_ns=command_completed_ns, window_ms=duration,
        schema='rocell.first_motion_capture_window.v1')
