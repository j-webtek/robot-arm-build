"""Bounded result envelope and diagnostic consistency, not process authentication."""
from rocell.application.first_motion_contract import canonical
from rocell.application.first_motion_result_review import review_completed_first_motion_trial
from rocell.arm.protocol import encode_line
from .first_motion_native_protocol import RESULT_SCHEMA,decode_request,validate_payload,_require
from .owned_worker_process import decode_owned_json,_hash

MAX_RESULT_BYTES=256*1024
COMPLETE={'REPORTED_WRIST_RESPONSE_REVIEW_REQUIRED','INSUFFICIENT_OR_UNEXPECTED_TELEMETRY'}
STATUSES=COMPLETE|{'NOT_OPENED','CANCELLED_BEFORE_OPEN','NATIVE_TRIAL_FAILED','NOT_SENT',
    'CANCELLED_BEFORE_WRITE','HELD_BEFORE_WRITE','WRITE_UNCERTAIN_NO_RETRY',
    'WRITE_COMPLETED_NOT_MOVEMENT_VERIFIED','TRIAL_FAILED_AFTER_WRITE','POST_CAPTURE_INCOMPLETE',
    'CLEANUP_UNCERTAIN','CLEANUP_UNCONFIRMED'}


def validate_result(value,*,wire):
    wire=decode_request(canonical(wire))
    request=validate_payload(wire['payload'])
    _require(type(value) is dict and set(value)=={'schema','attempt_id','request_sha256','child_result',
        'physical_authority','connected'},'COMMISSIONING_RESULT_FIELDS')
    _require(value['schema']==RESULT_SCHEMA and value['attempt_id']==wire['attempt_id']
        and value['request_sha256']==wire['request_sha256'] and value['physical_authority'] is False
        and value['connected'] is False,'COMMISSIONING_RESULT_CONTEXT')
    child=value['child_result']
    _require(type(child) is dict and set(child)=={'schema','claim_sha256','execution','physical_authority'}
        and child['schema']=='rocell.first_motion_native_child_result.v1'
        and child['physical_authority'] is False,'COMMISSIONING_CHILD_FIELDS')
    _hash(child['claim_sha256'])
    execution=child['execution']
    _require(type(execution) is dict and execution.get('schema')=='rocell.native_first_motion_execution.v1'
        and execution.get('request_sha256')==request.request_sha256
        and type(execution.get('status')) is str and execution['status'] in STATUSES
        and all(execution.get(k) is False for k in ('physical_movement_verified','physical_stop_verified','replay_allowed')),
        'COMMISSIONING_EXECUTION_CONTEXT')
    life=execution.get('lifecycle')
    _require(type(life) is dict and life.get('schema')=='rocell.first_motion_connection_lifecycle.v1'
        and life.get('request_sha256')==request.request_sha256 and life.get('connection_id')==wire['attempt_id']
        and life.get('physical_stop_verified') is False,'COMMISSIONING_LIFECYCLE_CONTEXT')
    for key,maximum in (('owned_handle_count',3),('pending_io_count',1),
                        ('confirmed_write_bytes',len(encode_line(request.to_dict()['command'])))):
        _require(type(life.get(key)) is int and 0<=life[key]<=maximum,'COMMISSIONING_LIFECYCLE_COUNTS')
    for category in ('reads','bytes'):
        counts=life.get('read_calls' if category=='reads' else 'read_bytes')
        _require(type(counts) is dict and set(counts)=={'baseline','post'},'COMMISSIONING_LIFECYCLE_READS')
        for phase in ('baseline','post'):
            _require(type(counts[phase]) is int and 0<=counts[phase]<=request.to_dict()['limits'][f'maximum_{phase}_{category}'],
                'COMMISSIONING_LIFECYCLE_BUDGET')
    clean=life.get('phase')=='CLOSED' and life['owned_handle_count']==life['pending_io_count']==0
    rebuilt=None
    if execution['status'] in COMPLETE:
        _require(clean and execution.get('errors')==[],'COMMISSIONING_COMPLETION_CONTRADICTION')
        rebuilt=review_completed_first_motion_trial(request,canonical(execution.get('trial')),
            expected_basis='RETAINED_PHYSICAL_CAPTURE')
        trial=execution['trial']
        _require(trial['status']==execution['status']
            and life['confirmed_write_bytes']==trial['write']['confirmed_write_bytes'],
            'COMMISSIONING_EXECUTION_TRIAL_MISMATCH')
        for phase in ('baseline','post'):
            _require(life['read_calls'][phase]==trial[phase]['read_calls']
                and life['read_bytes'][phase]==trial[phase]['raw']['bytes'],
                'COMMISSIONING_EXECUTION_CAPTURE_MISMATCH')
    # Failed forms are retained as diagnostics, not promoted to validated trials.
    return dict(claim_sha256=child['claim_sha256'],execution_status=execution['status'],
        status='COMPLETED_DATA_CONSISTENT' if rebuilt else 'FAILURE_DIAGNOSTIC_ONLY',
        rebuilt_trial=rebuilt,cleanup_reported_closed=clean,owned_process_receipt_verified=False,
        physical_movement_verified=False,physical_stop_verified=False,campaign_advance_allowed=False,replay_allowed=False)


def encode_result(child,wire):
    value=dict(schema=RESULT_SCHEMA,attempt_id=wire['attempt_id'],request_sha256=wire['request_sha256'],
        child_result=child,physical_authority=False,connected=False)
    raw=canonical(value)
    if len(raw)>MAX_RESULT_BYTES: raise ValueError('Commissioning result exceeds output budget')
    validate_result(value,wire=wire)
    return raw


def decode_result(raw,*,wire):
    value=decode_owned_json(raw,maximum=MAX_RESULT_BYTES)
    validate_result(value,wire=wire)
    return value
