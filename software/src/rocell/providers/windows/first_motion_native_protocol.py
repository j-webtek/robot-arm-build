"""Closed commissioning IPC data contract; parsing grants no launch authority.

Parent registration must independently verify executable/archive pins, fixed
argv, budgets and retained evidence. An internally consistent hash is not an
authenticated runtime, review, physical measurement or process receipt.
"""
import hashlib
from pathlib import Path
import re

from rocell.application.first_motion_contract import FirstMotionRequest, canonical
from .owned_worker_process import decode_owned_json, _path, _hash, WorkerProcessBudget

WORKER_ID='physical-first-motion-trial'
PAYLOAD_SCHEMA='rocell.first_motion_native_handoff.v1'
REQUEST_SCHEMA='rocell.owned_first_motion_native_request.v1'
RESULT_SCHEMA='rocell.owned_first_motion_native_result.v1'


def fixed_budget():
    return WorkerProcessBudget(run_timeout_ms=25000,cleanup_timeout_ms=2000,
        stdin_bytes=65536,stdout_bytes=256*1024,stderr_bytes=8192,process_count=1)


def _require(ok,code):
    if not ok: raise ValueError(code)


def validate_payload(value):
    fields={'schema','root','session_id','measurement_operation_id','first_motion_request',
            'launch_sha256','registration','review_authority_id'}
    _require(type(value) is dict and set(value)==fields,'COMMISSIONING_HANDOFF_FIELDS')
    _require(value['schema']==PAYLOAD_SCHEMA and type(value['root']) is str
        and type(value['registration']) is dict
        and value['review_authority_id']=='local-first-motion-review-v1','COMMISSIONING_HANDOFF_DOMAIN')
    _path(Path(value['root']))
    _hash(value['launch_sha256'])
    _require(type(value['session_id']) is str
        and re.fullmatch(r'wizard-[a-f0-9]{32}',value['session_id']) is not None,'COMMISSIONING_SESSION')
    _require(type(value['measurement_operation_id']) is str
        and re.fullmatch(r'operation-[a-f0-9]{32}',value['measurement_operation_id']) is not None,
        'COMMISSIONING_MEASUREMENT_SELECTION')
    _require(len(canonical(value['registration']))<=32768,'COMMISSIONING_RUNTIME_SIZE')
    request=FirstMotionRequest(canonical(value['first_motion_request']))
    body=request.to_dict()
    _require(body['deadline_monotonic_ns']-body['issued_monotonic_ns']>=27_000_000_000,
             'COMMISSIONING_PARENT_RUN_CLEANUP_BUDGET')
    return request


def decode_request(raw):
    wire=decode_owned_json(raw,maximum=65536)
    fields={'schema','worker_id','attempt_id','session_id','source_sha256','operation_sha256',
        'selected_identity_sha256','expires_at_monotonic_ns','parent_deadline_monotonic_ns',
        'payload','registration_sha256','request_sha256'}
    _require(type(wire) is dict and set(wire)==fields,'COMMISSIONING_WIRE_FIELDS')
    _require(wire['schema']==REQUEST_SCHEMA and wire['worker_id']==WORKER_ID,'COMMISSIONING_WIRE_DOMAIN')
    _require(hashlib.sha256(canonical({k:v for k,v in wire.items() if k!='request_sha256'})).hexdigest()
        ==wire['request_sha256'],'COMMISSIONING_WIRE_HASH')
    request=validate_payload(wire['payload'])
    body=request.to_dict()
    _require(wire['attempt_id']==body['attempt_id'] and wire['session_id']==wire['payload']['session_id']
        and wire['source_sha256']==body['references']['source_sha256']
        and wire['operation_sha256']==request.request_sha256
        and wire['selected_identity_sha256']==hashlib.sha256(canonical(body['usb_identity'])).hexdigest()
        and wire['registration_sha256']==hashlib.sha256(canonical(wire['payload']['registration'])).hexdigest(),
        'COMMISSIONING_WIRE_CONTEXT')
    for name in ('expires_at_monotonic_ns','parent_deadline_monotonic_ns'):
        _require(type(wire[name]) is int and wire[name]==body['deadline_monotonic_ns'],
                 'COMMISSIONING_WIRE_DEADLINE')
    return wire
