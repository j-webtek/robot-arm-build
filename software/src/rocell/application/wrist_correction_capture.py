"""Typed correction capture/validation adapter; no hardware construction."""
import base64
import time
from threading import Event
from rocell.providers.windows.wrist_correction_current_context import WristCorrectionContextRequest
from .endpoint_capture import _capture_owned_window
from .first_motion_capture_validation import _validate_clean_capture

SCHEMA='rocell.wrist_correction_capture.v1'


def capture_wrist_correction_window(request,phase,*,read_once,cancellation,
        clock_ns=time.monotonic_ns,idle_wait=None,command_completed_ns=None):
    if (type(request) is not WristCorrectionContextRequest or phase not in ('baseline','post')
            or type(cancellation) is not Event or not callable(read_once) or not callable(clock_ns)
            or (idle_wait is not None and not callable(idle_wait))):
        raise ValueError('Exact correction capture dependencies required')
    return _capture_owned_window(request,phase,read_once=read_once,cancellation=cancellation,
        clock_ns=clock_ns,idle_wait=idle_wait,command_completed_ns=command_completed_ns,
        window_ms=1000 if phase=='baseline' else 5000,schema=SCHEMA,runtime_body=request.runtime_body(),
        read_end_guard_ms=25,minimum_read_interval_ms=10)


def validate_wrist_correction_capture(request,capture,*,phase,command_completed_ns=None):
    if type(request) is not WristCorrectionContextRequest:
        raise ValueError('Exact correction capture request required')
    return _validate_clean_capture(request,capture,phase=phase,command_completed_ns=command_completed_ns,
                                   body=request.runtime_body(),schema=SCHEMA)


def correction_capture_original(request,capture,*,phase,command_completed_ns=None):
    """Project a validated collector envelope into the raw result-review schema.

    The caller must retain the full envelope too: this projection alone omits
    collector lifecycle diagnostics and cannot promote incomplete captures.
    """
    raw=validate_wrist_correction_capture(request,capture,phase=phase,command_completed_ns=command_completed_ns)
    return dict(raw_base64=base64.b64encode(raw).decode(),read_windows=capture['read_windows'],
                started_ns=capture['started_ns'],finished_ns=capture['window_deadline_ns'])
