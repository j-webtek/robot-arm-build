"""Bounded endpoint IPC envelope association, not an execution capability."""

import hashlib

from .endpoint_native_registration import REQUEST_SCHEMA,WORKER_ID,validate_payload,identity_hash,_require
from .owned_worker_process import decode_owned_json
from rocell.application.arm_bench_qualification_contract import _canonical


def decode_request(raw):
    wire = decode_owned_json(raw,maximum=65536)
    fields = {'schema','worker_id','attempt_id','session_id','source_sha256','operation_sha256',
              'selected_identity_sha256','expires_at_monotonic_ns','parent_deadline_monotonic_ns',
              'payload','registration_sha256','request_sha256'}
    _require(type(wire) is dict and set(wire)==fields,'ENDPOINT_WIRE_FIELDS')
    _require(wire['schema']==REQUEST_SCHEMA and wire['worker_id']==WORKER_ID,'ENDPOINT_WIRE_DOMAIN')
    _require(hashlib.sha256(_canonical({k:v for k,v in wire.items() if k!='request_sha256'})).hexdigest()
             == wire['request_sha256'],'ENDPOINT_WIRE_HASH')
    request = validate_payload(wire['payload'])
    body = request.to_dict()
    _require(wire['attempt_id']==body['attempt_id'] and wire['session_id']==wire['payload']['session_id']
             and wire['source_sha256']==body['references']['source_sha256']
             and wire['operation_sha256']==request.request_sha256
             and wire['selected_identity_sha256']==identity_hash(request)
             and wire['registration_sha256']==hashlib.sha256(_canonical(wire['payload']['registration'])).hexdigest(),
             'ENDPOINT_WIRE_CONTEXT')
    for name in ('expires_at_monotonic_ns','parent_deadline_monotonic_ns'):
        _require(type(wire[name]) is int and wire[name]==body['deadline_monotonic_ns'],'ENDPOINT_WIRE_DEADLINE')
    return wire
