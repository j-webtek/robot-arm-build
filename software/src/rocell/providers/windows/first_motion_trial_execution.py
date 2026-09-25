"""Commissioning native composition for a separately supervised child.

No CLI or wizard registration exists here. Parent admission must still validate
runtime/source pins, own the child process and retain diagnostics durably.
"""
from threading import Event
import time

from rocell.application.first_motion_contract import FirstMotionRequest
from rocell.application.first_motion_worker_claim import FirstMotionWorkerClaim
from rocell.application.first_motion_owned_trial import run_owned_first_motion_trial
from rocell.safety.first_motion_admission import FirstMotionPermit
from .first_motion_serial_api import WindowsFirstMotionSerialApi
from .first_motion_serial_connection import FirstMotionSerialConnection


def execute_native_first_motion_trial(request,permit,api,*,cancellation,worker_claim,
                                     current_source_sha256,current_runtime_sha256,
                                     clock_ns=time.monotonic_ns):
    """Consume the process-bound claim before opening; never retry an attempt."""
    if (type(request) is not FirstMotionRequest or type(permit) is not FirstMotionPermit
            or type(api) is not WindowsFirstMotionSerialApi or type(cancellation) is not Event
            or type(worker_claim) is not FirstMotionWorkerClaim
            or not api.matches_authorization(request,permit) or not callable(clock_ns)):
        raise ValueError('Exact admitted commissioning native composition required')
    worker_claim.consume(request,current_source_sha256=current_source_sha256,
        current_runtime_sha256=current_runtime_sha256,now_ns=clock_ns())
    connection = FirstMotionSerialConnection(request,api,clock_ns=clock_ns)
    result = dict(schema='rocell.native_first_motion_execution.v1',
        request_sha256=request.request_sha256,status='NOT_OPENED',trial=None,lifecycle=None,
        errors=[],physical_movement_verified=False,physical_stop_verified=False,replay_allowed=False)
    try:
        if cancellation.is_set():
            result['status']='CANCELLED_BEFORE_OPEN'
        else:
            connection.open()
            result['trial']=run_owned_first_motion_trial(request,permit,connection_id=api.connection_id,
                read_once=connection.read,write_once=connection.write_once,close_once=connection.close,
                cancellation=cancellation,basis='RETAINED_PHYSICAL_CAPTURE',clock_ns=clock_ns)
            result['status']=result['trial']['status']
    except Exception as error:
        result['errors'].append(type(error).__name__)
        result['status']='NATIVE_TRIAL_FAILED'
    finally:
        permit.revoke()
        try:
            cleanup=connection.close(2000)
            clean=cleanup.all_handles_closed and cleanup.pending_io_count==0
        except Exception as error:
            clean=False
            result['errors'].append(type(error).__name__)
        result['lifecycle']=connection.snapshot()
        if not clean:
            result['status_before_cleanup_failure']=result['status']
            result['status']='CLEANUP_UNCONFIRMED'
    return result
