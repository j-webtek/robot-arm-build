"""Reconstruct historical draft choices from a retained, host-owned capture.

Disk hashes establish association, not fresh servo state or physical accuracy.
The caller supplies current session/source/identity references, never browser data.
"""
import base64
import hashlib

from .first_motion_contract import canonical
from .powered_feedback_child_claim import _read
from .powered_arm_feedback_contract import PoweredFeedbackIntent, TELEMETRY_PURPOSE
from .wizard_powered_feedback_native_coordinator import PoweredFeedbackOutcome, TELEMETRY_ACTION
from .wizard_diagnostic_coordinator import decode_diagnostic_json
from .absolute_wrist_capture_drafts import draft_choices_from_capture
from rocell.providers.windows.owned_worker_process import OwnedWorkerResult
from rocell.providers.windows import powered_feedback_native_registration as protocol
from rocell.providers.windows.powered_feedback_native_wire import decode_request, validate_result


def choices_from_retained_telemetry(root, outcome, *, session_id, source_sha256, native_identity_sha256):
    if (type(outcome) is not PoweredFeedbackOutcome or type(outcome.process) is not OwnedWorkerResult
            or outcome.action_id != TELEMETRY_ACTION or outcome.persistence_error is not None):
        raise ValueError('Exact retained powered telemetry outcome required')
    process = outcome.process
    if (process.status != 'SUCCEEDED' or process.primary_error is not None or process.cleanup_errors
            or not process.process_created or not process.initial_thread_resumed
            or not process.tree_exit_confirmed or process.returncode != 0):
        raise ValueError('Completed owned capture process required')
    attempt = process.attempt_id
    records = {stage: _read(root, attempt, stage) for stage in ('prepared', 'consumed', 'claimed', 'outcome')}
    prepared, consumed, claimed, retained = (records[s][0] for s in ('prepared', 'consumed', 'claimed', 'outcome'))
    intent = PoweredFeedbackIntent(canonical(prepared['intent']))
    body = intent.to_dict()
    if (body['purpose'] != TELEMETRY_PURPOSE or body['session_id'] != session_id
            or body['attempt_id'] != attempt or body['references']['source_sha256'] != source_sha256
            or body['references']['native_identity_original_sha256'] != native_identity_sha256):
        raise ValueError('Historical capture unit/session/source mismatch')
    runtime_raw = base64.b64decode(prepared['originals_base64']['runtime_sha256'], validate=True)
    if hashlib.sha256(runtime_raw).hexdigest() != body['references']['runtime_sha256']:
        raise ValueError('Historical runtime original changed')
    payload = dict(schema=protocol.PAYLOAD_SCHEMA, root=str(root), intent=body,
        consumption_sha256=records['consumed'][1],
        registration=decode_diagnostic_json(runtime_raw, maximum=32768))
    wire = dict(schema=protocol.REQUEST_SCHEMA, worker_id=protocol.WORKER_ID,
        attempt_id=attempt, session_id=session_id, source_sha256=source_sha256,
        operation_sha256=intent.request_sha256, selected_identity_sha256=native_identity_sha256,
        expires_at_monotonic_ns=body['parent_deadline_monotonic_ns'],
        parent_deadline_monotonic_ns=body['parent_deadline_monotonic_ns'], payload=payload,
        registration_sha256=body['references']['runtime_sha256'])
    wire['request_sha256'] = hashlib.sha256(canonical(wire)).hexdigest()
    wire = decode_request(canonical(wire))
    if (wire['request_sha256'] != process.request_sha256
            or consumed.get('prepared_sha256') != records['prepared'][1]
            or consumed.get('request_sha256') != intent.request_sha256
            or claimed.get('consumption_sha256') != records['consumed'][1]
            or claimed.get('request_sha256') != intent.request_sha256
            or retained.get('consumption_sha256') != records['consumed'][1]
            or records['outcome'][1] != outcome.outcome_sha256
            or retained.get('process_status') != process.status
            or base64.b64decode(retained['stdout_base64'], validate=True) != process.stdout
            or base64.b64decode(retained['stderr_base64'], validate=True) != process.stderr):
        raise ValueError('Retained capture chain differs from owned receipt')
    result = decode_diagnostic_json(process.stdout, maximum=256*1024)
    if (canonical(result) != canonical(process.parsed_result)
            or result['child_result']['claim_sha256'] != records['claimed'][1]):
        raise ValueError('Retained child result/claim differs')
    validate_result(result, wire=wire)
    choices = draft_choices_from_capture(result['child_result']['observation'])
    if any(_read(root, attempt, stage) != records[stage] for stage in records):
        raise ValueError('Capture originals changed during reconstruction')
    return dict(choices, source_attempt_id=attempt, session_id=session_id,
        source_sha256=source_sha256, native_identity_sha256=native_identity_sha256,
        outcome_sha256=outcome.outcome_sha256, request_sha256=process.request_sha256,
        original_hashes={stage: item[1] for stage, item in records.items()})
