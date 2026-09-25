"""Retain a self-reported observation of one exact commissioning result.

This layer correlates evidence only. It does not authenticate an observer, prove
physical accuracy or stopping, modify the native result, or authorize advancement.
Failed and inconclusive observations are first-class retained records.
"""
import hashlib
import re
import base64

from .first_motion_contract import FirstMotionRequest, canonical
from .wizard_diagnostic_coordinator import decode_diagnostic_json
from .physical_onboarding_durability import (
    contained_path, publish_reservation_bytes, read_bounded_regular_file,
)

MAX_RESULT_BYTES = 256 * 1024
MAX_OBSERVATION_BYTES = 16384
FIELDS = frozenset(('observer_id', 'method', 'outcome', 'coverage', 'detail', 'limitations'))
MAX_OBSERVATIONS = 16


def observation_original(request, result_raw, values, *, recorded_ns):
    """Host supplies exact request/result bytes and recording time, not event time."""
    if (type(request) is not FirstMotionRequest or type(result_raw) is not bytes
            or type(values) is not dict or set(values) != FIELDS
            or type(recorded_ns) is not int or not 0 < recorded_ns < 2**63):
        raise ValueError('Exact request, retained result, observation fields and host time required')
    result = decode_diagnostic_json(result_raw, maximum=MAX_RESULT_BYTES)
    if (type(result) is not dict or result.get('schema') != 'rocell.first_motion_retained_result.v1'
            or result.get('request_sha256') != request.request_sha256):
        raise ValueError('Observation must reference the same commissioning result/request')
    if (type(values['observer_id']) is not str
            or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,63}', values['observer_id'])
            or type(values['method']) is not str or values['method'] not in ('LIVE_VISUAL', 'VIDEO_REVIEW')
            or type(values['outcome']) is not str or values['outcome'] not in ('EXPECTED_MOVEMENT', 'NO_MOVEMENT', 'WRONG_MOVEMENT', 'UNKNOWN')
            or type(values['coverage']) is not str or values['coverage'] not in ('ENTIRE_TRIAL', 'PARTIAL', 'UNKNOWN')
            or any(type(values[key]) is not str or not 1 <= len(values[key].strip()) <= 1024
                   for key in ('detail', 'limitations'))):
        raise ValueError('Explicit bounded observer, method, outcome, coverage and limitations required')
    original = canonical(dict(schema='rocell.first_motion_observation.v1',
        attempt_id=request.to_dict()['attempt_id'], request_sha256=request.request_sha256,
        result_sha256=hashlib.sha256(result_raw).hexdigest(),
        observation_method_reference_sha256=request.to_dict()['references']['independent_observation_method_sha256'],
        recorded_monotonic_ns=recorded_ns, observed_monotonic_ns=None,
        reported=dict(values), basis='SELF_REPORTED_OBSERVATION',
        observer_identity_verified=False, physical_accuracy_verified=False,
        physical_movement_verified=False, physical_stop_verified=False,
        campaign_advance_allowed=False, replay_allowed=False))
    if len(original) > MAX_OBSERVATION_BYTES:
        raise ValueError('Encoded observation exceeds byte budget')
    return original


def record_observation(request, result_raw, values, *, root, operation_id, recorded_ns):
    """Exclusive retention; partial files remain diagnostic, never auto-recovered."""
    if type(operation_id) is not str or not re.fullmatch(r'operation-[a-f0-9]{32}', operation_id):
        raise ValueError('Host recording operation ID required')
    raw = observation_original(request, result_raw, values, recorded_ns=recorded_ns)
    prefix = operation_id+'-first-motion-observation-'
    publish_reservation_bytes(root, prefix+'result.json', result_raw, maximum_bytes=MAX_RESULT_BYTES)
    publish_reservation_bytes(root, prefix+'original.json', raw, maximum_bytes=MAX_OBSERVATION_BYTES)
    return dict(status='OBSERVATION_RECORDED_NOT_QUALIFIED', operation_id=operation_id,
        attempt_id=request.to_dict()['attempt_id'], request_sha256=request.request_sha256,
        result_sha256=hashlib.sha256(result_raw).hexdigest(), observation_sha256=hashlib.sha256(raw).hexdigest(),
        outcome=values['outcome'], coverage=values['coverage'],
        physical_movement_verified=False, campaign_advance_allowed=False)


def load_observation(request, *, root, operation_id, expected_observation_sha256, expected_result_sha256):
    """Reconstitute unchanged evidence from host-selected receipt identities.

    Recording time is deliberately preserved, not refreshed. Historical records
    remain readable after a motion request expires; this never renews authority.
    """
    if (type(operation_id) is not str or not re.fullmatch(r'operation-[a-f0-9]{32}', operation_id)
            or any(type(value) is not str or not re.fullmatch(r'[a-f0-9]{64}', value)
                   for value in (expected_observation_sha256, expected_result_sha256))):
        raise ValueError('Exact host-selected observation receipt required')
    prefix = operation_id+'-first-motion-observation-'
    result_raw = read_bounded_regular_file(contained_path(root, prefix+'result.json', label='observed result'), maximum_bytes=MAX_RESULT_BYTES)
    raw = read_bounded_regular_file(contained_path(root, prefix+'original.json', label='observation original'), maximum_bytes=MAX_OBSERVATION_BYTES)
    if (hashlib.sha256(raw).hexdigest() != expected_observation_sha256
            or hashlib.sha256(result_raw).hexdigest() != expected_result_sha256):
        raise ValueError('Observation or referenced result changed')
    value = decode_diagnostic_json(raw, maximum=MAX_OBSERVATION_BYTES)
    try:
        rebuilt = observation_original(request, result_raw, value['reported'], recorded_ns=value['recorded_monotonic_ns'])
    except (KeyError, TypeError) as error:
        raise ValueError('Malformed observation original') from error
    if rebuilt != raw:
        raise ValueError('Observation binding or declarations changed')
    return value


def export_observations(*, root, records):
    """Bounded original-byte bundle; deduplicate identical requests/results.

    Host-selected receipts only. Bytes are encoded so diagnostic text redaction
    cannot silently change evidence named by a hash. This bundle is intended for
    the assigned local diagnostic folder, not automatic third-party transmission.
    """
    if type(records) is not tuple or not 0 < len(records) <= MAX_OBSERVATIONS:
        raise ValueError('One to sixteen host-selected observation receipts required')
    blobs, associations = {}, []
    def retain(raw):
        digest = hashlib.sha256(raw).hexdigest()
        blobs[digest] = dict(bytes=len(raw), base64_chunks=[
            base64.b64encode(raw[i:i+32768]).decode('ascii') for i in range(0, len(raw), 32768)])
        return digest
    for request, receipt in records:
        original = load_observation(request, root=root, operation_id=receipt['operation_id'],
            expected_observation_sha256=receipt['observation_sha256'], expected_result_sha256=receipt['result_sha256'])
        result_raw = read_bounded_regular_file(contained_path(root,
            receipt['operation_id']+'-first-motion-observation-result.json', label='observed result'), maximum_bytes=MAX_RESULT_BYTES)
        if hashlib.sha256(result_raw).hexdigest() != receipt['result_sha256']:
            raise ValueError('Observed result changed during export')
        associations.append(dict(operation_id=receipt['operation_id'],
            request_sha256=retain(request.canonical_bytes), result_sha256=retain(result_raw),
            observation_sha256=retain(canonical(original))))
    raw = canonical(dict(schema='rocell.first_motion_observation_export.v1',
        associations=associations, originals=blobs, physical_movement_verified=False,
        campaign_advance_allowed=False, replay_allowed=False))
    if len(raw) > 900*1024:
        raise ValueError('Complete observation originals exceed export budget; no truncation allowed')
    return raw
