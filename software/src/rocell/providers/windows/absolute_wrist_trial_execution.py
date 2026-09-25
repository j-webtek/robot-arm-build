"""Process-bound absolute native composition; not registered for public launch."""
from threading import Event
import time

from rocell.application.absolute_wrist_owned_trial import _run_absolute_wrist_trial
from rocell.application.absolute_wrist_worker_claim import AbsoluteWristWorkerClaim
from rocell.safety.absolute_wrist_admission import AbsoluteWristPermit
from rocell.safety.absolute_wrist_review_authority import AbsoluteWristIntent
from .absolute_wrist_serial_api import WindowsAbsoluteWristSerialApi
from .absolute_wrist_serial_connection import AbsoluteWristSerialConnection


class _NativeBindingAdapter:
    """Leave the one-use dispatch claim to the exact native IO-token boundary."""
    def __init__(self, request, permit, api):
        self._request, self._permit, self._api = request, permit, api

    def bind_baseline(self, raw, windows, *, started_ns, finished_ns):
        return self._permit.bind_owned_baseline(self._request, self._api.connection_id,
            self._api._port_name, raw, windows, started_ns=started_ns, finished_ns=finished_ns)

    def consume_command(self):
        # Despite the shared-loop method name, this is data selection only.
        # WindowsEndpointSerialApi.submit_io consumes before WriteFile.
        return self._permit.selected_payload()

    def revoke(self):
        self._permit.revoke()


def execute_native_absolute_wrist_trial(request, permit, api, *, worker_claim,
        current_source_sha256, current_runtime_sha256, cancellation, clock_ns=time.monotonic_ns):
    if (type(request) is not AbsoluteWristIntent or type(permit) is not AbsoluteWristPermit
            or type(api) is not WindowsAbsoluteWristSerialApi
            or type(worker_claim) is not AbsoluteWristWorkerClaim or type(cancellation) is not Event
            or not api.matches_authorization(request, permit) or not callable(clock_ns)):
        raise ValueError('Exact owned absolute native composition required')
    try:
        worker_claim.consume(request, current_source_sha256=current_source_sha256,
            current_runtime_sha256=current_runtime_sha256, now_ns=clock_ns())
        connection = AbsoluteWristSerialConnection(request, api, clock_ns=clock_ns)
    except Exception:
        permit.revoke()
        raise
    result = dict(schema='rocell.absolute_wrist_native_child_result.v1',
        claim_sha256=worker_claim.claim_sha256, status='NOT_OPENED', result=None,
        lifecycle=None, errors=[], physical_authority=False)
    try:
        if cancellation.is_set():
            result['status'] = 'CANCELLED_BEFORE_OPEN'
        else:
            connection.open()
            result['result'] = _run_absolute_wrist_trial(request, _NativeBindingAdapter(request, permit, api),
                read_once=connection.read, write_once=connection.write_once, close_once=connection.close,
                cancellation=cancellation, basis='RETAINED_PHYSICAL_CAPTURE', clock_ns=clock_ns, idle_wait=None)
            result['status'] = result['result']['status']
    except Exception as exc:
        result['errors'].append(type(exc).__name__)
        result['status'] = 'NATIVE_TRIAL_FAILED'
    finally:
        permit.revoke()
        try:
            cleanup = connection.close(2000)
            clean = cleanup.all_handles_closed and cleanup.pending_io_count == 0
        except Exception as exc:
            clean = False
            result['errors'].append(type(exc).__name__)
        result['lifecycle'] = connection.snapshot()
        if not clean:
            result['status'] = 'CLEANUP_UNCONFIRMED'
    return result
