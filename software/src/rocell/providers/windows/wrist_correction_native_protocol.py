"""Closed correction IPC contract, without launch or motor authority.

Large original captures stay in the assigned store. Their ordered hashes and
the signed plan are part of the operation identity, not caller command fields.
The child must authenticate the plan and consume its owned permit separately.
"""
import hashlib
from pathlib import Path

from rocell.application.first_motion_contract import canonical
from rocell.safety.absolute_wrist_review_authority import AbsoluteWristIntent
from .wrist_correction_current_context import WristCorrectionContextRequest
from .owned_worker_process import decode_owned_json, _path, _hash, WorkerProcessBudget

WORKER_ID = 'physical-wrist-correction-trial'
PAYLOAD_SCHEMA = 'rocell.wrist_correction_native_handoff.v1'
REQUEST_SCHEMA = 'rocell.owned_wrist_correction_native_request.v1'
RESULT_SCHEMA = 'rocell.wrist_correction_native_result_reference.v1'


def digest(value):
    return hashlib.sha256(value).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def fixed_budget():
    return WorkerProcessBudget(run_timeout_ms=25000, cleanup_timeout_ms=2000,
        stdin_bytes=65536, stdout_bytes=256*1024, stderr_bytes=8192, process_count=1)


def evidence_manifest(originals):
    """Fingerprint immutable originals; this does not validate their telemetry."""
    require(type(originals) is list and 2 <= len(originals) <= 8, 'Bounded original pairs required')
    rows = []
    for pair in originals:
        require(type(pair) is tuple and len(pair) == 2, 'Exact original pair required')
        request, raw = pair
        require(type(request) is AbsoluteWristIntent and type(raw) is bytes and
                0 < len(raw) <= 512*1024, 'Bounded immutable original required')
        rows.append(dict(request_sha256=request.request_sha256, trial_sha256=digest(raw)))
    validate_manifest(rows)
    return rows


def validate_manifest(rows):
    require(type(rows) is list and 2 <= len(rows) <= 8, 'Bounded evidence manifest required')
    for row in rows:
        require(type(row) is dict and set(row) == {'request_sha256', 'trial_sha256'},
                'Exact evidence hashes required')
        for value in row.values():
            _hash(value)
    for field in ('request_sha256', 'trial_sha256'):
        require(len({row[field] for row in rows}) == len(rows), 'Duplicate evidence original')


def validate_payload(value):
    require(type(value) is dict and set(value) == {
        'schema', 'root', 'context', 'launch_sha256', 'registration',
        'review_authority_id', 'plan_sha256', 'originals', 'expected_basis'}, 'Exact correction payload required')
    require(value['schema'] == PAYLOAD_SCHEMA and
        value['review_authority_id'] == 'local-wrist-correction-review-v1', 'Wrong correction domain')
    require(type(value['root']) is str and type(value['registration']) is dict, 'Exact root/registration required')
    _path(Path(value['root']))
    _hash(value['launch_sha256']); _hash(value['plan_sha256'])
    validate_manifest(value['originals'])
    require(value['expected_basis'] in ('SYNTHETIC_WIRE_REHEARSAL', 'RETAINED_PHYSICAL_CAPTURE'), 'Wrong evidence basis')
    request = WristCorrectionContextRequest(canonical(value['context']))
    body = request.to_dict()
    require(body['deadline_ns'] - body['issued_ns'] >= 27_000_000_000, 'Insufficient supervisor lifetime')
    registration = canonical(value['registration'])
    require(len(registration) <= 32768 and digest(registration) == body['references']['runtime_sha256'],
        'Runtime registration reference mismatch')
    return request


def verify_originals(payload, *, originals, plan_raw):
    """Recheck store bytes after resolving them; hashes are not authentication."""
    validate_payload(payload)
    require(type(plan_raw) is bytes and 0 < len(plan_raw) <= 65536, 'Bounded plan original required')
    require(digest(plan_raw) == payload['plan_sha256'] and
        evidence_manifest(originals) == payload['originals'], 'Correction evidence changed')


def decode_request(raw):
    wire = decode_owned_json(raw, maximum=65536)
    require(type(wire) is dict and set(wire) == {
        'schema', 'worker_id', 'attempt_id', 'session_id', 'source_sha256', 'operation_sha256',
        'selected_identity_sha256', 'expires_at_monotonic_ns', 'parent_deadline_monotonic_ns',
        'payload', 'registration_sha256', 'request_sha256'}, 'Exact correction wire required')
    require(wire['schema'] == REQUEST_SCHEMA and wire['worker_id'] == WORKER_ID, 'Wrong correction worker domain')
    require(wire['request_sha256'] == digest(canonical({k:v for k,v in wire.items() if k != 'request_sha256'})),
        'Correction wire hash mismatch')
    body = validate_payload(wire['payload']).to_dict()
    # Include every payload field: a context-only hash would not bind the plan.
    require(wire['operation_sha256'] == digest(canonical(wire['payload'])) and
        wire['attempt_id'] == body['attempt_id'] and wire['session_id'] == body['session_id'] and
        wire['source_sha256'] == body['references']['source_sha256'] and
        wire['registration_sha256'] == body['references']['runtime_sha256'] and
        wire['selected_identity_sha256'] == digest(canonical(body['usb_identity'])), 'Correction association mismatch')
    for name in ('expires_at_monotonic_ns', 'parent_deadline_monotonic_ns'):
        require(type(wire[name]) is int and wire[name] == body['deadline_ns'], 'Correction deadline mismatch')
    return wire
