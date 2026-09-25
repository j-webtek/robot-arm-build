"""Campaign-specific native IPC contract; not a registered launch mechanism.

The reviewed intent is the only command source. Decoding hashes associates
bytes, not authenticated evidence or clearance. Native package verification,
one-use process/leg claims and stop qualification remain separate requirements.
"""
import hashlib
from pathlib import Path

from rocell.application.first_motion_contract import canonical
from rocell.safety.positional_campaign_authority import PositionalCampaignIntent
from .owned_worker_process import WorkerProcessBudget, decode_owned_json, _hash, _path

WORKER_ID = 'physical-positional-campaign'
PAYLOAD_SCHEMA = 'rocell.positional_campaign_native_handoff.v1'
REQUEST_SCHEMA = 'rocell.owned_positional_campaign_request.v1'
RESULT_SCHEMA = 'rocell.owned_positional_campaign_result.v1'


def fixed_budget(schema=None):
    """Aggregate upper caps, always clipped by the immutable intent deadline.

    One process, no descendants. Large raw results must be retained separately;
    the IPC result is a bounded receipt, not an expanded multi-leg capture tree.
    This budget does not extend any eight-second leg or five-second observation.
    """
    from rocell.safety.positional_campaign_authority import BASE_SEQUENCE_SCHEMA, ROLL_PERSISTENCE_SCHEMA, ROLL_LONG_FIXED_SCHEMA, ROLL_FRAMED_SCHEMA, ROLL_VARIATION_SCHEMA
    return WorkerProcessBudget(run_timeout_ms=48000 if schema=='rocell.attended_positional_intent.v18' else 58000 if schema in (ROLL_PERSISTENCE_SCHEMA,ROLL_LONG_FIXED_SCHEMA,ROLL_FRAMED_SCHEMA,ROLL_VARIATION_SCHEMA,BASE_SEQUENCE_SCHEMA) else 28000, cleanup_timeout_ms=2000,
        stdin_bytes=65536, stdout_bytes=256*1024, stderr_bytes=8192, process_count=1)


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def validate_payload(value):
    fields = {'schema', 'root', 'campaign_intent', 'launch_sha256',
        'registration', 'review_authority_id'}
    _require(type(value) is dict and set(value) == fields, 'Exact campaign handoff fields required')
    _require(value['schema'] == PAYLOAD_SCHEMA and type(value['root']) is str
        and type(value['registration']) is dict
        and value['review_authority_id'] == 'local-positional-campaign-review-v1',
        'Wrong campaign handoff domain')
    _path(Path(value['root']))
    _hash(value['launch_sha256'])
    _require(value['launch_sha256'] != '0'*64, 'Non-placeholder campaign launch reference required')
    registration = canonical(value['registration'])
    _require(len(registration) <= 32768, 'Campaign registration exceeds budget')
    intent = PositionalCampaignIntent(canonical(value['campaign_intent']))
    _require(hashlib.sha256(registration).hexdigest() == intent.to_dict()['references']['runtime_sha256'],
        'Campaign runtime differs from reviewed reference')
    return intent


def decode_request(raw):
    wire = decode_owned_json(raw, maximum=65536)
    fields = {'schema', 'worker_id', 'attempt_id', 'session_id', 'source_sha256',
        'operation_sha256', 'selected_identity_sha256', 'expires_at_monotonic_ns',
        'parent_deadline_monotonic_ns', 'payload', 'registration_sha256', 'request_sha256'}
    _require(set(wire) == fields, 'Exact campaign wire fields required')
    _require(wire['schema'] == REQUEST_SCHEMA and wire['worker_id'] == WORKER_ID,
        'Wrong campaign worker/request domain')
    _hash(wire['request_sha256'])
    _require(hashlib.sha256(canonical({k: v for k, v in wire.items() if k != 'request_sha256'})).hexdigest()
        == wire['request_sha256'], 'Campaign wire hash mismatch')
    intent = validate_payload(wire['payload'])
    body = intent.to_dict()
    _require(wire['attempt_id'] == body['campaign_id'] and wire['session_id'] == body['session_id']
        and wire['source_sha256'] == body['references']['source_sha256']
        and wire['operation_sha256'] == intent.sha256
        and wire['selected_identity_sha256'] == hashlib.sha256(canonical(body['usb_identity'])).hexdigest()
        and wire['registration_sha256'] == body['references']['runtime_sha256'],
        'Campaign worker request association mismatch')
    for field in ('expires_at_monotonic_ns', 'parent_deadline_monotonic_ns'):
        _require(type(wire[field]) is int and wire[field] == body['deadline_ns'],
            'Campaign worker deadline mismatch')
    return wire


def decode_result(raw, *, request_raw):
    """Compact IPC association only; parent reconstructs retained trial bytes."""
    wire = decode_request(request_raw)
    result = decode_owned_json(raw, maximum=8192)
    _require(type(result) is dict and set(result) == {'schema', 'intent_sha256', 'claim_sha256',
        'trial_sha256', 'trial_bytes', 'physical_authority'}, 'Exact campaign receipt required')
    _require(result['schema'] == RESULT_SCHEMA and result['intent_sha256'] == wire['operation_sha256']
        and result['physical_authority'] is False and type(result['trial_bytes']) is int
        and 0 < result['trial_bytes'] <= 2_097_152, 'Campaign receipt association mismatch')
    _hash(result['claim_sha256'])
    _hash(result['trial_sha256'])
    return result
