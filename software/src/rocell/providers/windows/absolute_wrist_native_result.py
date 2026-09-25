"""Bounded absolute worker result wire with independent endpoint reconstruction."""
import base64

from rocell.application.first_motion_contract import canonical
from rocell.application.absolute_wrist_result_review import review_absolute_wrist_result
from .absolute_wrist_native_protocol import RESULT_SCHEMA, decode_request, validate_payload, _require
from .owned_worker_process import decode_owned_json, _hash

MAX_BYTES = 256*1024
ENDPOINT_STATUSES = {'REPORTED_SETTLED', 'HELD_TRANSPORT_FAULT', 'HELD_FEEDBACK_INVALID',
    'HELD_OTHER_JOINT_CHANGED', 'HELD_WRIST_EXCURSION', 'HELD_NO_RESPONSE',
    'HELD_TARGET_MISSED', 'HELD_NOT_SETTLED'}
FAILURE_STATUSES = {'NOT_OPENED', 'CANCELLED_BEFORE_OPEN', 'NATIVE_TRIAL_FAILED',
    'NOT_SENT', 'CANCELLED_BEFORE_WRITE', 'HELD_BEFORE_WRITE', 'FAILED_AFTER_WRITE',
    'WRITE_UNCERTAIN_NO_RETRY', 'CAPTURED', 'CLEANUP_UNCERTAIN',
    'CLEANUP_UNCONFIRMED', 'RESULT_NOT_RECONSTRUCTABLE'}


def _errors(value):
    _require(type(value) is list and len(value) <= 16
        and all(type(e) is str and len(e) <= 256 for e in value), 'Bounded error list required')


def _lifecycle(child, request):
    lifecycle = child['lifecycle']
    fields = {'schema','phase','request_sha256','connection_id','owned_handle_count','pending_io_count',
              'read_calls','read_bytes','confirmed_write_bytes','late_cleanup_read_base64','errors','physical_stop_verified'}
    _require(type(lifecycle) is dict and set(lifecycle) == fields
        and lifecycle['schema'] == 'rocell.absolute_wrist_connection_lifecycle.v1'
        and lifecycle['request_sha256'] == request.request_sha256
        and lifecycle['connection_id'] == request.to_dict()['attempt_id']
        and lifecycle['physical_stop_verified'] is False, 'Absolute lifecycle association mismatch')
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
    _errors(lifecycle['errors'])
    return clean


def validate_result(value, *, wire):
    _require(len(canonical(value)) <= MAX_BYTES, 'Absolute result exceeds output budget')
    wire = decode_request(canonical(wire))
    request = validate_payload(wire['payload'])
    _require(type(value) is dict and set(value) == {'schema', 'attempt_id', 'request_sha256',
        'child_result', 'physical_authority', 'connected'}, 'Exact absolute result fields required')
    _require(value['schema'] == RESULT_SCHEMA and value['attempt_id'] == wire['attempt_id']
        and value['request_sha256'] == wire['request_sha256']
        and value['physical_authority'] is False and value['connected'] is False,
        'Absolute result association mismatch')
    child = value['child_result']
    _require(type(child) is dict and set(child) == {'schema', 'claim_sha256', 'status',
        'result', 'lifecycle', 'errors', 'physical_authority'}, 'Exact absolute child fields required')
    _require(child['schema'] == 'rocell.absolute_wrist_native_child_result.v1'
        and type(child['status']) is str and child['status'] in ENDPOINT_STATUSES | FAILURE_STATUSES
        and child['physical_authority'] is False, 'Absolute child status/domain mismatch')
    _hash(child['claim_sha256'])
    _errors(child['errors'])
    clean = _lifecycle(child, request)
    owned, rebuilt = child['result'], None
    if owned is not None:
        flags = {'motion_authorized', 'physical_movement_verified', 'physical_stop_verified',
                 'campaign_advance_allowed', 'replay_allowed'}
        _require(type(owned) is dict and set(owned) == flags | {'schema', 'status', 'trial', 'review', 'errors'}
            and owned['schema'] == 'rocell.owned_absolute_wrist_trial.v1'
            and type(owned['status']) is str and owned['status'] in ENDPOINT_STATUSES | FAILURE_STATUSES
            and all(owned[k] is False for k in flags), 'Exact non-authorizing owned result required')
        _errors(owned['errors'])
        # Reconstruct any claimed review, including a held endpoint. A child
        # cannot turn a target miss into a pass by changing its summary.
        if owned['review'] is not None:
            rebuilt = review_absolute_wrist_result(request, canonical(owned['trial']),
                                                  expected_basis='RETAINED_PHYSICAL_CAPTURE')
            _require(canonical(owned['review']) == canonical(rebuilt), 'Child endpoint review differs from originals')
            endpoint = rebuilt['endpoint']['status']
            expected = endpoint if endpoint == 'REPORTED_SETTLED' else 'HELD_' + endpoint
            _require(owned['status'] == expected, 'Owned endpoint label mismatch')
            trial, lifecycle = owned['trial'], child['lifecycle']
            _require(lifecycle['confirmed_write_bytes'] == trial['write']['confirmed_bytes'],
                     'Lifecycle/write accounting mismatch')
            for phase in ('baseline', 'post'):
                _require(lifecycle['read_calls'][phase] == trial[phase]['read_calls']
                    and lifecycle['read_bytes'][phase] == trial[phase]['raw']['bytes'],
                    'Lifecycle/capture accounting mismatch')
        else:
            _require(owned['status'] not in ENDPOINT_STATUSES, 'Endpoint label requires reconstructed evidence')
        _require(child['status'] == owned['status'] or child['status'] == 'CLEANUP_UNCONFIRMED',
                 'Child/owned status mismatch')
    else:
        _require(child['status'] in {'NOT_OPENED', 'CANCELLED_BEFORE_OPEN', 'NATIVE_TRIAL_FAILED',
            'CLEANUP_UNCONFIRMED'}, 'Missing owned trial for claimed outcome')
    if child['status'] in {'NOT_OPENED', 'CANCELLED_BEFORE_OPEN'}:
        lifecycle = child['lifecycle']
        _require(lifecycle['confirmed_write_bytes'] == 0
            and all(n == 0 for n in lifecycle['read_calls'].values())
            and all(n == 0 for n in lifecycle['read_bytes'].values())
            and lifecycle['late_cleanup_read_base64'] == '', 'Unopened outcome has IO accounting')
    if child['status'] == 'REPORTED_SETTLED':
        _require(rebuilt is not None and clean and not child['errors']
            and not owned['errors'] and not child['lifecycle']['errors'],
            'Settled result has incomplete cleanup or errors')
    consistent = rebuilt is not None and clean and child['status'] in ENDPOINT_STATUSES
    return dict(status='COMPLETED_DATA_CONSISTENT' if consistent else 'FAILURE_DIAGNOSTIC_ONLY',
        rebuilt_trial=rebuilt, claim_sha256=child['claim_sha256'], cleanup_reported_closed=clean,
        owned_process_receipt_verified=False, physical_movement_verified=False,
        campaign_advance_allowed=False, replay_allowed=False)


def encode_result(child, *, wire):
    value = dict(schema=RESULT_SCHEMA, attempt_id=wire['attempt_id'], request_sha256=wire['request_sha256'],
                 child_result=child, physical_authority=False, connected=False)
    validate_result(value, wire=wire)
    return canonical(value)


def decode_result(raw, *, wire):
    value = decode_owned_json(raw, maximum=MAX_BYTES)
    validate_result(value, wire=wire)
    return value
