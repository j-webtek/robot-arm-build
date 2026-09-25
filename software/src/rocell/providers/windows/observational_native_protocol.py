"""Closed observational IPC contract; decoding does not authorize launch.

The parent/child must separately verify pinned executable/package bytes, owned
process claims and current signed records. No command or measured geometry is
accepted in this handoff: the single target is derived inside the connection.
"""
import hashlib
from pathlib import Path

from rocell.application.first_motion_contract import canonical
from rocell.safety.observational_review_authority import ObservationalIntent
from .owned_worker_process import decode_owned_json, _path, _hash, WorkerProcessBudget

WORKER_ID = 'physical-observational-wrist-trial'
PAYLOAD_SCHEMA = 'rocell.observational_native_handoff.v1'
REQUEST_SCHEMA = 'rocell.owned_observational_native_request.v1'
RESULT_SCHEMA = 'rocell.owned_observational_native_result.v1'


def fixed_budget():
    return WorkerProcessBudget(run_timeout_ms=25000, cleanup_timeout_ms=2000,
        stdin_bytes=65536, stdout_bytes=256*1024, stderr_bytes=8192, process_count=1)


def _require(ok, message):
    if not ok:
        raise ValueError(message)


def validate_payload(value):
    fields = {'schema','root','observational_intent','launch_sha256','registration','review_authority_id'}
    _require(type(value) is dict and set(value) == fields, 'Exact observational handoff fields required')
    _require(value['schema'] == PAYLOAD_SCHEMA and type(value['root']) is str
        and type(value['registration']) is dict
        and value['review_authority_id'] == 'local-observational-review-v1', 'Wrong observational handoff domain')
    _path(Path(value['root']))
    _hash(value['launch_sha256'])
    registration_raw = canonical(value['registration'])
    _require(len(registration_raw) <= 32768, 'Observational registration too large')
    request = ObservationalIntent(canonical(value['observational_intent']))
    body = request.to_dict()
    _require(body['deadline_ns']-body['issued_ns'] >= 27_000_000_000,
             'Insufficient supervised run/cleanup lifetime')
    _require(hashlib.sha256(registration_raw).hexdigest() == body['references']['runtime_sha256'],
             'Registration differs from signed runtime reference')
    return request


def decode_request(raw):
    wire = decode_owned_json(raw, maximum=65536)
    fields = {'schema','worker_id','attempt_id','session_id','source_sha256','operation_sha256',
              'selected_identity_sha256','expires_at_monotonic_ns','parent_deadline_monotonic_ns',
              'payload','registration_sha256','request_sha256'}
    _require(type(wire) is dict and set(wire) == fields, 'Exact observational wire fields required')
    _require(wire['schema'] == REQUEST_SCHEMA and wire['worker_id'] == WORKER_ID,
             'Wrong observational wire domain')
    _hash(wire['request_sha256'])
    _require(hashlib.sha256(canonical({k:v for k,v in wire.items() if k != 'request_sha256'})).hexdigest()
             == wire['request_sha256'], 'Observational wire hash mismatch')
    request = validate_payload(wire['payload'])
    body = request.to_dict()
    _require(wire['attempt_id'] == body['attempt_id'] and wire['session_id'] == body['session_id']
        and wire['source_sha256'] == body['references']['source_sha256']
        and wire['operation_sha256'] == request.request_sha256
        and wire['selected_identity_sha256'] == hashlib.sha256(canonical(body['usb_identity'])).hexdigest()
        and wire['registration_sha256'] == body['references']['runtime_sha256'],
        'Observational wire context mismatch')
    for name in ('expires_at_monotonic_ns','parent_deadline_monotonic_ns'):
        _require(type(wire[name]) is int and wire[name] == body['deadline_ns'], 'Observational deadline mismatch')
    return wire
