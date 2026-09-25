"""Process-claim-bound native composition, not registered for CLI/wizard launch."""
import hashlib
from threading import Event
import time

from rocell.application.observational_worker_claim import ObservationalWorkerClaim
from rocell.application.observational_owned_trial import run_owned_observational_trial
from rocell.application.physical_onboarding_durability import contained_path, read_bounded_regular_file
from rocell.application.wizard_diagnostic_coordinator import decode_diagnostic_json
from rocell.safety.observational_review_authority import ObservationalIntent
from rocell.safety.observational_admission import ObservationalPermit
from .observational_serial_api import WindowsObservationalSerialApi
from .observational_serial_connection import ObservationalSerialConnection


def execute_native_observational_trial(request, permit, api, *, worker_claim,
        current_source_sha256, current_runtime_sha256, cancellation, clock_ns=time.monotonic_ns):
    if (type(request) is not ObservationalIntent or type(permit) is not ObservationalPermit
            or type(api) is not WindowsObservationalSerialApi
            or type(worker_claim) is not ObservationalWorkerClaim or type(cancellation) is not Event
            or not api.matches_authorization(request, permit) or not callable(clock_ns)):
        raise ValueError('Exact observational native composition required')
    try:
        worker_claim.consume(request, current_source_sha256=current_source_sha256,
            current_runtime_sha256=current_runtime_sha256, now_ns=clock_ns())
        connection = ObservationalSerialConnection(request, api, clock_ns=clock_ns)
    except Exception:
        permit.revoke()
        raise
    result = dict(schema='rocell.observational_native_child_result.v1',
        claim_sha256=worker_claim.claim_sha256, status='NOT_OPENED', trial=None,
        selection_original=None, lifecycle=None, errors=[], physical_authority=False)
    try:
        if cancellation.is_set():
            result['status'] = 'CANCELLED_BEFORE_OPEN'
        else:
            connection.open()
            trial = result['trial'] = run_owned_observational_trial(request, permit,
                connection_id=api.connection_id, port_name=api._port_name,
                read_once=connection.read, write_once=connection.write_once, close_once=connection.close,
                cancellation=cancellation, basis='RETAINED_PHYSICAL_CAPTURE', clock_ns=clock_ns)
            result['status'] = trial['status']
            if trial['selection'] is not None:
                # Read the original from the process claim's fixed root, never
                # a path returned by a child/browser or a different workspace.
                raw = read_bounded_regular_file(contained_path(worker_claim._root,
                    request.to_dict()['attempt_id']+'-observational-command-selection.json',
                    label='owned observational selection'), maximum_bytes=16384)
                if hashlib.sha256(raw).hexdigest() != trial['selection']['selection_sha256']:
                    raise ValueError('Original observational selection changed')
                result['selection_original'] = decode_diagnostic_json(raw, maximum=16384)
    except Exception as error:
        result['errors'].append(type(error).__name__)
        result['status'] = 'NATIVE_TRIAL_FAILED'
    finally:
        permit.revoke()
        try:
            cleanup = connection.close(2000)
            clean = cleanup.all_handles_closed and cleanup.pending_io_count == 0
        except Exception as error:
            clean = False
            result['errors'].append(type(error).__name__)
        result['lifecycle'] = connection.snapshot()
        if not clean:
            result['status'] = 'CLEANUP_UNCONFIRMED'
    return result
