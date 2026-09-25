"""Bounded final-readback collection; no open, write, retry or admission.

The caller supplies the already-owned connection's read method and retains the
entire envelope even on failure. Dispatch integration must account for these
reads in the connection's existing cumulative baseline budgets.
"""
import time
from threading import Event
from .endpoint_capture import _capture_owned_window
from .first_motion_capture_validation import _validate_clean_capture
from .wrist_correction_final_readback import MAX_BYTES,MAX_READS,MAX_WINDOW_NS,validate_final_readback
from rocell.providers.windows.wrist_correction_current_context import WristCorrectionContextRequest

SCHEMA='rocell.wrist_correction_final_capture.v2'
LEGACY_SCHEMA='rocell.wrist_correction_final_capture.v1'


def _body(request):
    if type(request) is not WristCorrectionContextRequest:
        raise ValueError('Exact correction request required')
    body=request.runtime_body()
    body['limits'].update(maximum_baseline_bytes=MAX_BYTES,maximum_baseline_reads=MAX_READS,
        maximum_baseline_ms=MAX_WINDOW_NS//1_000_000)
    return body


def capture_final_readback(request,*,read_once,cancellation,clock_ns=time.monotonic_ns,idle_wait=None):
    """One read-only window capped at 200 ms; no unobserved idle tail or retry."""
    if (not callable(read_once) or type(cancellation) is not Event or not callable(clock_ns)
            or (idle_wait is not None and not callable(idle_wait))):
        raise ValueError('Exact bounded final-capture dependencies required')
    return _capture_owned_window(request,'baseline',read_once=read_once,cancellation=cancellation,
        clock_ns=clock_ns,idle_wait=idle_wait,command_completed_ns=None,
        window_ms=MAX_WINDOW_NS//1_000_000,schema=SCHEMA,runtime_body=_body(request),
        # The shared collector additionally reserves 25 ms for an owned read.
        # This final window has a 5 ms extra guard and 15 ms admission spacing.
        read_end_guard_ms=5,minimum_read_interval_ms=15,finish_at_read_guard=True)


def validate_final_capture(request,capture,originals,*,basis,baseline_samples,
        selection_sha256,now_ns):
    body=_body(request)
    early=type(capture) is dict and capture.get('schema')==SCHEMA
    raw=_validate_clean_capture(request,capture,phase='baseline',command_completed_ns=None,
        body=body,schema=SCHEMA if early else LEGACY_SCHEMA,
        early_end_guard_ns=30_000_000 if early else None)
    result=validate_final_readback(originals,basis=basis,baseline_samples=baseline_samples,
        selection_sha256=selection_sha256,usb_identity=request.to_dict()['usb_identity'],
        raw=raw,windows=capture['read_windows'],started_ns=capture['started_ns'],
        finished_ns=capture['observation_end_ns'] if early else capture['window_deadline_ns'],
        now_ns=now_ns,review_deadline_ns=body['deadline_ns'])
    if now_ns<capture['finished_ns']:
        raise ValueError('Final capture validation precedes actual collector completion')
    return result
