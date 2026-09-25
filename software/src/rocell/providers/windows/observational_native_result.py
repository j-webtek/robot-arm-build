"""Bounded observational worker results; process authentication stays separate."""
import base64
from rocell.application.first_motion_contract import canonical
from rocell.application.observational_result_review import review_completed_observational_trial
from .observational_native_protocol import RESULT_SCHEMA, decode_request, validate_payload, _require
from .owned_worker_process import decode_owned_json, _hash

MAX_BYTES = 256*1024
STATUSES = {'NOT_OPENED','CANCELLED_BEFORE_OPEN','NATIVE_TRIAL_FAILED',
    'CANCELLED_BEFORE_WRITE','HELD_BEFORE_WRITE','WRITE_UNCERTAIN_NO_RETRY',
    'AWAITING_OPERATOR_OBSERVATION','TRIAL_FAILED_AFTER_WRITE','POST_CAPTURE_INCOMPLETE',
    'CLEANUP_UNCERTAIN','CLEANUP_UNCONFIRMED'}


def validate_result(value, *, wire):
    wire = decode_request(canonical(wire))
    request = validate_payload(wire['payload'])
    _require(type(value) is dict and set(value) == {'schema','attempt_id','request_sha256',
        'child_result','physical_authority','connected'}, 'Exact observational result fields required')
    _require(value['schema'] == RESULT_SCHEMA and value['attempt_id'] == wire['attempt_id']
        and value['request_sha256'] == wire['request_sha256'] and value['physical_authority'] is False
        and value['connected'] is False, 'Observational result context mismatch')
    child = value['child_result']
    _require(type(child) is dict and set(child) == {'schema','claim_sha256','status','trial',
        'selection_original','lifecycle','errors','physical_authority'}, 'Exact observational child fields required')
    _require(child['schema'] == 'rocell.observational_native_child_result.v1'
        and type(child['status']) is str and child['status'] in STATUSES
        and child['physical_authority'] is False, 'Observational child domain mismatch')
    _hash(child['claim_sha256'])
    _require(type(child['errors']) is list and len(child['errors']) <= 16
        and all(type(e) is str and len(e) <= 256 for e in child['errors']), 'Bounded child errors required')
    lifecycle = child['lifecycle']
    fields = {'schema','phase','request_sha256','connection_id','owned_handle_count','pending_io_count',
              'read_calls','read_bytes','confirmed_write_bytes','late_cleanup_read_base64','errors','physical_stop_verified'}
    _require(type(lifecycle) is dict and set(lifecycle) == fields
        and lifecycle['schema'] == 'rocell.observational_connection_lifecycle.v1'
        and lifecycle['request_sha256'] == request.request_sha256
        and lifecycle['connection_id'] == wire['attempt_id']
        and lifecycle['physical_stop_verified'] is False, 'Observational lifecycle association mismatch')
    for key, maximum in (('owned_handle_count',3), ('pending_io_count',1), ('confirmed_write_bytes',512)):
        _require(type(lifecycle[key]) is int and 0 <= lifecycle[key] <= maximum, 'Invalid lifecycle accounting')
    limits = request.runtime_body()['limits']
    _require(lifecycle['phase'] in {'UNOPENED','OPENING','OPEN','FAILED','CLOSED','CLEANUP_UNCONFIRMED'}
        and type(lifecycle['errors']) is list and len(lifecycle['errors']) <= 16,
        'Invalid lifecycle phase/errors')
    late = lifecycle['late_cleanup_read_base64']
    _require(type(late) is str and len(late) <= 87384, 'Cleanup read budget exceeded')
    _require(len(base64.b64decode(late, validate=True)) <= 65536, 'Cleanup read byte budget exceeded')
    for category in ('reads','bytes'):
        counts = lifecycle['read_calls' if category == 'reads' else 'read_bytes']
        _require(type(counts) is dict and set(counts) == {'baseline','post'}, 'Exact capture counters required')
        for phase in ('baseline','post'):
            _require(type(counts[phase]) is int and 0 <= counts[phase] <= limits[f'maximum_{phase}_{category}'],
                     'Capture counter exceeds budget')
    clean = lifecycle['phase'] == 'CLOSED' and lifecycle['owned_handle_count'] == lifecycle['pending_io_count'] == 0
    rebuilt = None
    if child['status'] == 'AWAITING_OPERATOR_OBSERVATION':
        _require(clean and child['errors'] == [] and lifecycle['errors'] == [], 'Completed child has cleanup/errors')
        rebuilt = review_completed_observational_trial(request, canonical(child['trial']),
            canonical(child['selection_original']), expected_basis='RETAINED_PHYSICAL_CAPTURE')
        trial = child['trial']
        _require(lifecycle['confirmed_write_bytes'] == trial['write']['confirmed_write_bytes'],
                 'Lifecycle/write count mismatch')
        for phase in ('baseline','post'):
            _require(lifecycle['read_calls'][phase] == trial[phase]['read_calls']
                and lifecycle['read_bytes'][phase] == trial[phase]['raw']['bytes'], 'Lifecycle/capture count mismatch')
    # Failure payloads remain bounded originals. No promotion based on a plausible
    # endpoint or complete-looking capture inside a failed/uncertain attempt.
    return dict(status='COMPLETED_DATA_CONSISTENT' if rebuilt else 'FAILURE_DIAGNOSTIC_ONLY',
        rebuilt_trial=rebuilt, claim_sha256=child['claim_sha256'], cleanup_reported_closed=clean,
        owned_process_receipt_verified=False, physical_movement_verified=False,
        campaign_advance_allowed=False, replay_allowed=False)


def encode_result(child, *, wire):
    value = dict(schema=RESULT_SCHEMA, attempt_id=wire['attempt_id'], request_sha256=wire['request_sha256'],
                 child_result=child, physical_authority=False, connected=False)
    raw = canonical(value)
    if len(raw) > MAX_BYTES:
        raise ValueError('Observational result exceeds output budget')
    validate_result(value, wire=wire)
    return raw


def decode_result(raw, *, wire):
    value = decode_owned_json(raw, maximum=MAX_BYTES)
    validate_result(value, wire=wire)
    return value
