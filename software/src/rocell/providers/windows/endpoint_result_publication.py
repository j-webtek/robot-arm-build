"""Retain endpoint IPC originals before interpretation; no launch or device APIs.

Caller is the trusted parent supervisor. Process ownership/exit facts must never
be populated from a browser request or child-supplied fields. A durable report
is diagnostic evidence only, not authorization to repeat a command.
"""

import hashlib
import base64
from pathlib import Path

from rocell.application.arm_bench_qualification_contract import _canonical
from rocell.application.endpoint_worker_claim import verify_endpoint_worker_receipt
from rocell.application.physical_onboarding_durability import publish_bytes, PublicationMode
from .endpoint_native_registration import validate_payload
from .endpoint_native_wire import decode_request
from .endpoint_native_result import decode_result, validate_result, MAX_RESULT_BYTES


def publish_supervised_endpoint_result(root, *, registration, request, result):
    """Adapt the actual supervisor receipt, not UI-supplied process facts.

    Pure retention: this function cannot create or resume a worker. Kept separate
    from admission so failed attempts remain exportable after their deadlines.
    """
    from .owned_worker_process import OwnedWorkerResult, owned_request_wire, owned_registration_document
    from .endpoint_native_registration import REQUEST_SCHEMA, RESULT_SCHEMA
    if type(result) is not OwnedWorkerResult:
        raise ValueError('Exact owned supervisor receipt required')
    # Do not reread executable/source pins here: changed files after a run must
    # not prevent retaining its original diagnostic streams.
    if registration.request_schema!=REQUEST_SCHEMA or registration.result_schema!=RESULT_SCHEMA:
        raise ValueError('Endpoint supervisor protocol required')
    raw, digest = owned_request_wire(registration,request,deadline_ns=request.expires_at_ns)
    wire = decode_request(raw)
    if _canonical(wire['payload']['registration'])!=_canonical(owned_registration_document(registration)):
        raise ValueError('Supervisor runtime association mismatch')
    if result.attempt_id!=request.attempt_id or result.request_sha256!=digest:
        raise ValueError('Supervisor receipt request association mismatch')
    # Cleanup/timeout errors must not be hidden by exit code zero or a valid
    # endpoint observation. Those observations remain available in the summary.
    completion = (result.status=='SUCCEEDED' and result.primary_error is None
                  and result.cleanup_errors==() and result.process_created
                  and result.initial_thread_resumed and result.tree_exit_confirmed)
    return publish_endpoint_result(root,request_raw=raw,stdout=result.stdout,stderr=result.stderr,
        owned_process_id=result.owned_process_id,
        returncode=result.returncode if result.returncode is not None else -1,
        process_tree_closed=completion,finished_ns=result.finished_monotonic_ns)


def publish_endpoint_result(root, *, request_raw, stdout, stderr, owned_process_id,
                            returncode, process_tree_closed, finished_ns):
    """Publish raw streams first, including malformed/failed child results.

    Immutable names make repeated publication fail rather than overwrite evidence.
    An interrupted publication may leave originals without a final report. Such
    a tail is retained and must not trigger a launch retry.
    """
    for raw, maximum in ((request_raw,65536),(stdout,MAX_RESULT_BYTES),(stderr,8192)):
        if type(raw) is not bytes or len(raw)>maximum:
            raise ValueError('Endpoint IPC stream exceeds publication budget')
    if type(process_tree_closed) is not bool or type(returncode) is not int:
        raise ValueError('Parent process completion facts required')
    wire = decode_request(request_raw)
    request = validate_payload(wire['payload'])
    prefix = wire['attempt_id']+'-endpoint-'
    originals = {}
    for name, raw in (('request.json',request_raw),('stdout.bin',stdout),('stderr.bin',stderr)):
        # Encode even empty streams as nonempty immutable documents. The digest
        # and byte count describe original IPC bytes, not this storage wrapper.
        filename = prefix+name+'.original.json'
        stored = _canonical({'bytes':len(raw),'base64':base64.b64encode(raw).decode('ascii')})
        publish_bytes(Path(root),filename,stored,mode=PublicationMode.IMMUTABLE,
                      maximum_bytes=2*MAX_RESULT_BYTES)
        originals[name] = {'file':filename,'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}
    report = {'schema':'rocell.endpoint_retained_result.v1','request_sha256':request.request_sha256,
              'status':'RESULT_REJECTED','originals':originals,'summary':None,
              'returncode':returncode,'process_tree_closed':process_tree_closed,
              'errors':[],'physical_movement_verified':False,'physical_stop_verified':False,
              'replay_allowed':False}
    try:
        value = decode_result(stdout,wire=wire)
        summary = validate_result(value,wire=wire)
        verify_endpoint_worker_receipt(wire['payload']['root'],request,
            claim_sha256=summary['claim_sha256'],launch_sha256=wire['payload']['launch_sha256'],
            owned_process_id=owned_process_id,
            runtime_sha256=hashlib.sha256(_canonical(wire['payload']['registration'])).hexdigest(),
            finished_ns=finished_ns)
        report['summary'] = summary
        report['status'] = ('RESULT_RETAINED' if returncode==0 and process_tree_closed
                            else 'PROCESS_COMPLETION_UNCONFIRMED')
    except (ValueError, OSError, RuntimeError) as exc:
        report['errors'].append({'stage':'result_validation','code':type(exc).__name__})
    path = publish_bytes(Path(root),prefix+'report.json',_canonical(report),
                         mode=PublicationMode.IMMUTABLE,maximum_bytes=MAX_RESULT_BYTES)
    return path,report
