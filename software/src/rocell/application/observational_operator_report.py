"""Simple operator reports tied to an exact retained observational trial.

No precision measurements or calibrated images are required. Reports are
self-reported evidence, never a substitute for the native telemetry original.
"""
import hashlib
import re

from rocell.safety.observational_review_authority import ObservationalIntent
from .first_motion_contract import canonical
from .wizard_diagnostic_coordinator import decode_diagnostic_json
from .physical_onboarding_durability import publish_reservation_bytes

FIELDS = frozenset(('observer_id', 'outcome', 'covered_trial', 'detail'))


def record_operator_report(request, result_raw, values, *, root, operation_id, recorded_ns):
    if (type(request) is not ObservationalIntent or type(result_raw) is not bytes
            or type(values) is not dict or set(values) != FIELDS
            or type(operation_id) is not str or not re.fullmatch(r'operation-[a-f0-9]{32}', operation_id)
            or type(recorded_ns) is not int or not 0 < recorded_ns < 2**63):
        raise ValueError('Exact host request, original result, observation and recording identity required')
    result = decode_diagnostic_json(result_raw, maximum=256*1024)
    if (type(result) is not dict or canonical(result) != result_raw
            or result.get('schema') != 'rocell.observational_retained_result.v1'
            or result.get('attempt_id') != request.to_dict()['attempt_id']
            or result.get('request_sha256') != request.request_sha256):
        raise ValueError('Observation belongs to a different or malformed retained trial')
    if (type(values['observer_id']) is not str
            or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,63}', values['observer_id'])
            or type(values['outcome']) is not str
            or values['outcome'] not in ('EXPECTED_MOVEMENT', 'NO_MOVEMENT', 'WRONG_MOVEMENT', 'UNKNOWN')
            or type(values['covered_trial']) is not bool
            or type(values['detail']) is not str or len(values['detail']) > 1024):
        raise ValueError('Bounded observer, outcome, coverage and optional notes required')
    result_sha = hashlib.sha256(result_raw).hexdigest()
    observation = dict(schema='rocell.observational_operator_report.v1',
        operation_id=operation_id, attempt_id=request.to_dict()['attempt_id'],
        request_sha256=request.request_sha256, result_sha256=result_sha,
        reported=dict(values), recorded_ns=recorded_ns, observed_ns=None,
        basis='SELF_REPORTED_OBSERVATION', observer_identity_verified=False,
        physical_accuracy_verified=False, physical_stop_verified=False,
        campaign_advance_allowed=False, replay_allowed=False)
    raw = canonical(observation)
    prefix = operation_id+'-observational-operator-'
    # Save request and result beside the observation for independent reconstruction.
    for suffix, original, maximum in (('request.json', request.canonical_bytes, 8192),
            ('result.json', result_raw, 256*1024), ('report.json', raw, 16384)):
        publish_reservation_bytes(root, prefix+suffix, original, maximum_bytes=maximum)
    return dict(status='OBSERVATION_RECORDED', observation=observation,
        observation_sha256=hashlib.sha256(raw).hexdigest(),
        functional_assessment_pending=True, physical_movement_verified=False,
        campaign_advance_allowed=False, replay_allowed=False)


def export_operator_reports(*, root, receipts):
    """Export exact host-selected originals; deduplicate repeated trial data."""
    import base64
    from .physical_onboarding_durability import contained_path, read_bounded_regular_file
    if type(receipts) is not tuple or not 0 < len(receipts) <= 16:
        raise ValueError('One to sixteen host-owned observation receipts required')
    originals, associations = {}, []
    for receipt in receipts:
        observation = receipt['observation']
        operation = observation['operation_id']
        if not re.fullmatch(r'operation-[a-f0-9]{32}', operation):
            raise ValueError('Host observation identity required')
        association = dict(operation_id=operation)
        for kind, digest, maximum in (
                ('request', observation['request_sha256'], 8192),
                ('result', observation['result_sha256'], 256*1024),
                ('report', receipt['observation_sha256'], 16384)):
            raw = read_bounded_regular_file(contained_path(root,
                operation+'-observational-operator-'+kind+'.json', label='operator evidence'),
                maximum_bytes=maximum)
            if hashlib.sha256(raw).hexdigest() != digest:
                raise ValueError('Retained observational original changed')
            if kind == 'report' and raw != canonical(observation):
                raise ValueError('Host observation receipt changed')
            originals[digest] = dict(bytes=len(raw), base64_chunks=[
                base64.b64encode(raw[i:i+32768]).decode('ascii') for i in range(0, len(raw), 32768)])
            association[kind+'_sha256'] = digest
        if 'assessment_sha256' in receipt:
            raw = read_bounded_regular_file(contained_path(root,
                operation+'-observational-assessment.json', label='functional assessment'), maximum_bytes=128*1024)
            digest = hashlib.sha256(raw).hexdigest()
            if digest != receipt['assessment_sha256'] or raw != canonical(receipt['assessment']):
                raise ValueError('Retained functional assessment changed')
            originals[digest] = dict(bytes=len(raw), base64_chunks=[
                base64.b64encode(raw[i:i+32768]).decode('ascii') for i in range(0, len(raw), 32768)])
            association['assessment_sha256'] = digest
        associations.append(association)
    raw = canonical(dict(schema='rocell.observational_operator_export.v1',
        originals=originals, associations=associations, campaign_advance_allowed=False, replay_allowed=False))
    if len(raw) > 900*1024:
        raise ValueError('Observation export exceeds budget; no originals truncated')
    return raw
