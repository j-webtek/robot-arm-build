"""Retain actual parent receipts and bounded IPC originals without permitting replay."""
import base64
import hashlib
from pathlib import Path

from rocell.application.first_motion_contract import canonical
from rocell.application.observational_worker_claim import verify_observational_worker_receipt
from rocell.application.physical_onboarding_durability import publish_bytes, PublicationMode
from .observational_native_protocol import decode_request, validate_payload, REQUEST_SCHEMA, RESULT_SCHEMA
from .observational_native_result import decode_result, validate_result, MAX_BYTES
from .owned_worker_process import OwnedWorkerResult, owned_request_wire, owned_registration_document


def publish_supervised_observational_result(root, *, registration, request, result):
    """Trusted-parent-only retention, including rejected/uncertain child output.

    No current-file pin check belongs here: a changed file must not erase evidence
    from an already attempted run. Publication failure never implies retrying motion.
    """
    if (type(result) is not OwnedWorkerResult or registration.request_schema != REQUEST_SCHEMA
            or registration.result_schema != RESULT_SCHEMA):
        raise ValueError('Exact observational supervisor receipt required')
    raw, digest = owned_request_wire(registration, request, deadline_ns=request.expires_at_ns)
    wire = decode_request(raw)
    intent = validate_payload(wire['payload'])
    if (canonical(wire['payload']['registration']) != canonical(owned_registration_document(registration))
            or result.attempt_id != request.attempt_id
            or result.request_sha256 not in (None, '', digest)):
        raise ValueError('Supervisor receipt association mismatch')
    # Preflight failures can precede wire hashing, but cannot claim a created process.
    if result.request_sha256 != digest and (result.process_created or result.stdout or result.stderr):
        raise ValueError('Created process requires exact wire association')
    prefix = request.attempt_id+'-observational-'
    originals = {}
    streams = (('request', raw, 65536), ('stdout', result.stdout, MAX_BYTES), ('stderr', result.stderr, 8192))
    for _, data, maximum in streams:
        if type(data) is not bytes or len(data) > maximum:
            raise ValueError('IPC original exceeds retention budget')
    for name, data, _ in streams:
        filename = prefix+name+'.original.json'
        publish_bytes(Path(root), filename, canonical(dict(bytes=len(data),
            base64=base64.b64encode(data).decode('ascii'))),
            mode=PublicationMode.IMMUTABLE, maximum_bytes=2*MAX_BYTES)
        originals[name] = dict(file=filename, bytes=len(data), sha256=hashlib.sha256(data).hexdigest())
    report = dict(schema='rocell.observational_retained_result.v1',
        attempt_id=request.attempt_id, request_sha256=intent.request_sha256,
        status='RESULT_REJECTED', originals=originals, summary=None,
        supervisor=result.to_dict(),
        claim_receipt_verified=False, physical_movement_verified=False,
        physical_stop_verified=False, campaign_advance_allowed=False, replay_allowed=False, errors=[])
    report['supervisor']['cleanup_errors'] = list(result.cleanup_errors)
    try:
        summary = validate_result(decode_result(result.stdout, wire=wire), wire=wire)
        verify_observational_worker_receipt(wire['payload']['root'], intent,
            claim_sha256=summary['claim_sha256'], launch_sha256=wire['payload']['launch_sha256'],
            owned_process_id=result.owned_process_id,
            runtime_sha256=hashlib.sha256(canonical(wire['payload']['registration'])).hexdigest(),
            finished_ns=result.finished_monotonic_ns)
        report['summary'] = summary
        report['claim_receipt_verified'] = True
        complete = (result.status == 'SUCCEEDED' and result.primary_error is None
            and result.cleanup_errors == () and result.process_created
            and result.initial_thread_resumed and result.tree_exit_confirmed and result.returncode == 0)
        report['status'] = 'RESULT_RETAINED' if complete else 'PROCESS_COMPLETION_UNCONFIRMED'
    except (ValueError, OSError, RuntimeError) as error:
        report['errors'].append(dict(stage='result_validation', code=type(error).__name__))
    path = publish_bytes(Path(root), prefix+'report.json', canonical(report),
        mode=PublicationMode.IMMUTABLE, maximum_bytes=MAX_BYTES)
    return path, report
