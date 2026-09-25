"""Endpoint metadata through the existing contained no-actuation diagnostic.

No new child entry, command, transport or raw native fallback is introduced.
The host supplies current cancellation and log-retention callbacks. Acquisition
time remains the child's original time, never the time the parent received it.
"""

from pathlib import Path
from threading import Event
import time

from .endpoint_trial_contract import EndpointTrialRequest
from .endpoint_worker_preparation import MINIMUM_PREPARATION_REMAINING_NS
from .wizard_diagnostic_coordinator import DiagnosticProcessRunner
from .wizard_native_arm_metadata import decode_controller_snapshot


def acquire_supervised_metadata(*, runner, cell_id, cancel, cutoff_ns, retain,
                                check_current, clock_ns=time.monotonic_ns):
    """Shared real acquisition/retention path for endpoint use and timing probes.

    This function needs no motion request or fabricated qualification evidence.
    Timing probes use the same path with their own log association. Returned
    snapshot times are untouched; the caller still validates identity and age.
    """
    if check_current() is not None or type(cancel) is not Event or cancel.is_set():
        raise ValueError('Current uncancelled metadata operation required')
    if type(cutoff_ns) is not int or not 0 < clock_ns() < cutoff_ns:
        raise ValueError('Metadata work cutoff expired or invalid')
    try:
        result = runner.run('inspect_native_arm_metadata',
            {'metadata_only':True,'power_disconnected':False},cell_id=cell_id,
            cancel=cancel,progress=lambda message:None,deadline_monotonic_ns=cutoff_ns)
    except Exception as error:
        retain({'status':'METADATA_SUPERVISION_FAILED','error_type':type(error).__name__,
                'physical_authority':False})
        raise
    if retain({'result':result,'physical_authority':False}) is not None:
        raise ValueError('Metadata retention not confirmed')
    if (cancel.is_set() or check_current() is not None or clock_ns() >= cutoff_ns
            or result.get('status') != 'SUCCEEDED' or result.get('worker_exit_code') != 0):
        raise ValueError('Metadata failed, cancelled, changed or exceeded its budget')
    steps = result.get('steps',[])
    if (len(steps) != 1 or steps[0].get('name') != 'native_arm_metadata_snapshot'
            or steps[0].get('exit_code') != 0):
        raise ValueError('Exact supervised metadata snapshot required')
    return decode_controller_snapshot(steps[0]['report'],'physical')


class SupervisedEndpointMetadataFactory:
    def __init__(self, *, workspace, source_sha256, cell_id, cancellation_reader,
                 retain, check_current, clock_ns=time.monotonic_ns):
        if (type(cell_id) is not str or not 1 <= len(cell_id) <= 128
                or not all(callable(v) for v in (cancellation_reader,retain,check_current,clock_ns))):
            raise ValueError('Trusted metadata supervision dependencies required')
        self._runner = DiagnosticProcessRunner(Path(workspace),expected_source_sha256=source_sha256)
        self._source,self._cell = source_sha256,cell_id
        self._cancel,self._retain,self._current,self._clock = cancellation_reader,retain,check_current,clock_ns

    def __call__(self, request):
        if (type(request) is not EndpointTrialRequest
                or request.to_dict()['references']['source_sha256'] != self._source):
            raise ValueError('Metadata request source changed')
        def acquire():
            cutoff = request.to_dict()['deadline_monotonic_ns']-MINIMUM_PREPARATION_REMAINING_NS
            def retain(record):
                return self._retain({'request_sha256':request.request_sha256,**record})
            return acquire_supervised_metadata(runner=self._runner,cell_id=self._cell,
                cancel=self._cancel(),cutoff_ns=cutoff,retain=retain,
                check_current=self._current,clock_ns=self._clock)
        return acquire
