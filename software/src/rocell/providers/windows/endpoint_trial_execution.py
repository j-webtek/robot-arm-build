"""Compose an admitted facade, handle owner and one endpoint trial.

Trusted native child entry only. There is no CLI or wizard registration here.
The parent still needs source/runtime admission, exclusive process claiming,
protected review issuance, cancellation supervision and durable result retention.
"""

from threading import Event
import time

from rocell.application.endpoint_owned_trial import run_owned_endpoint_trial
from rocell.application.endpoint_trial_contract import EndpointTrialRequest
from rocell.application.endpoint_worker_claim import EndpointWorkerClaim
from rocell.safety.bench_endpoint import BenchEndpointPermit
from .endpoint_serial_api import WindowsEndpointSerialApi
from .endpoint_serial_connection import EndpointSerialConnection


def execute_native_endpoint_trial(request, permit, api, *, cancellation,
                                  presence_expiry_reader, worker_claim,
                                  current_source_sha256, current_runtime_sha256,
                                  clock_ns=time.monotonic_ns):
    if (type(request) is not EndpointTrialRequest or type(permit) is not BenchEndpointPermit
            or type(api) is not WindowsEndpointSerialApi or type(cancellation) is not Event
            or not api.matches_authorization(request,permit)
            or type(worker_claim) is not EndpointWorkerClaim
            or not callable(presence_expiry_reader) or not callable(clock_ns)):
        raise ValueError('Exact admitted native trial composition required')
    worker_claim.consume(request,current_source_sha256=current_source_sha256,
                         current_runtime_sha256=current_runtime_sha256,now_ns=clock_ns())
    connection = EndpointSerialConnection(request,api,clock_ns=clock_ns)
    result = {'schema':'rocell.native_endpoint_execution.v1','request_sha256':request.request_sha256,
              'status':'NOT_OPENED','trial':None,'lifecycle':None,'errors':[],
              'physical_movement_verified':False,'physical_stop_verified':False,'replay_allowed':False}
    try:
        if cancellation.is_set():
            result['status'] = 'CANCELLED_BEFORE_OPEN'
        else:
            connection.open()
            result['trial'] = run_owned_endpoint_trial(request,permit,connection_id=api.connection_id,
                read_once=connection.read,write_once=connection.write_once,close_once=connection.close,
                presence_expiry_reader=presence_expiry_reader,cancellation=cancellation,
                basis='RETAINED_PHYSICAL_CAPTURE',clock_ns=clock_ns)
            result['status'] = result['trial']['status']
    except Exception as error:
        result['errors'].append(type(error).__name__)
        result['status'] = 'NATIVE_TRIAL_FAILED'
    finally:
        permit.revoke()
        # close is idempotent and never resubmits cancellation or handle closes.
        # This also covers exceptions between open and the trial's own finally.
        cleanup = connection.close(2000)
        result['lifecycle'] = connection.snapshot()
        if not cleanup.all_handles_closed or cleanup.pending_io_count:
            result['status_before_cleanup_failure'] = result['status']
            result['status'] = 'CLEANUP_UNCONFIRMED'
    return result
