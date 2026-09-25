"""Explicit, evidence-bound functional-response review; never motion authority.

Host integration must reconstitute the assessment from original streams,
observation and its own supervisor receipt. A self-reported reviewer decision
does not authenticate a person or establish calibrated accuracy/physical stopping.
"""
import hashlib
import re
import base64
from .first_motion_contract import canonical
from .physical_onboarding_durability import publish_reservation_bytes
from .wizard_diagnostic_coordinator import decode_diagnostic_json

REVIEW_CHECKS = frozenset(('observer_identity_reviewed', 'method_compliance_reviewed',
                          'observation_timing_reviewed', 'discrepancies_resolved'))


def decision_original(assessment_raw, values, *, recorded_ns):
    if (type(assessment_raw) is not bytes or type(values) is not dict
            or set(values) != REVIEW_CHECKS | {'reviewer_id','decision','rationale'}
            or type(recorded_ns) is not int or not 0 < recorded_ns < 2**63):
        raise ValueError('Exact assessment, explicit review fields and host time required')
    assessment = decode_diagnostic_json(assessment_raw, maximum=128*1024)
    if (type(assessment) is not dict or canonical(assessment) != assessment_raw
            or assessment.get('schema') != 'rocell.first_motion_qualification_assessment.v1'
            or assessment.get('status') not in ('HELD','READY_FOR_EXPLICIT_QUALIFICATION_REVIEW')
            or type(assessment.get('holds')) is not list
            or any(assessment.get(key) is not False for key in ('physical_movement_verified',
                'physical_accuracy_verified','physical_stop_verified','campaign_advance_allowed'))):
        raise ValueError('Canonical non-authorizing assessment required')
    if (type(values['reviewer_id']) is not str or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,63}', values['reviewer_id'])
            or type(values['decision']) is not str or values['decision'] not in ('UNKNOWN','REJECT','ACCEPT_FUNCTIONAL_RESPONSE')
            or type(values['rationale']) is not str or not 1 <= len(values['rationale'].strip()) <= 1024
            or any(type(values[key]) is not bool for key in REVIEW_CHECKS)):
        raise ValueError('Bounded reviewer, decision, rationale and explicit Boolean checks required')
    if values['decision'] == 'ACCEPT_FUNCTIONAL_RESPONSE':
        if (assessment['status'] != 'READY_FOR_EXPLICIT_QUALIFICATION_REVIEW' or assessment['holds']
                or not all(values[key] for key in REVIEW_CHECKS)):
            raise ValueError('Acceptance cannot override a hold or an incomplete review')
    raw = canonical(dict(schema='rocell.first_motion_qualification_decision.v1',
        assessment_sha256=hashlib.sha256(assessment_raw).hexdigest(),
        recorded_monotonic_ns=recorded_ns, reported_review=dict(values),
        scope='ONE_RETAINED_WRIST_FUNCTIONAL_RESPONSE', reviewer_identity_authenticated=False,
        physical_accuracy_verified=False, physical_stop_verified=False,
        campaign_advance_allowed=False, motion_authorized=False, replay_allowed=False))
    if len(raw) > 16384: raise ValueError('Encoded decision exceeds byte budget')
    return raw


def record_qualification_decision(assessment_raw, values, *, root, operation_id, recorded_ns, revalidate):
    """Recompute before publication; retain partial writes without auto-recovery."""
    if (type(operation_id) is not str or not re.fullmatch(r'operation-[a-f0-9]{32}', operation_id)
            or not callable(revalidate)):
        raise ValueError('Host operation identity and original-evidence revalidation required')
    raw = decision_original(assessment_raw, values, recorded_ns=recorded_ns)
    if revalidate() != assessment_raw:
        raise ValueError('Assessment changed before review publication')
    prefix = operation_id+'-first-motion-qualification-'
    publish_reservation_bytes(root, prefix+'assessment.json', assessment_raw, maximum_bytes=128*1024)
    publish_reservation_bytes(root, prefix+'decision.json', raw, maximum_bytes=16384)
    if revalidate() != assessment_raw:
        raise ValueError('Evidence changed during publication; retained files are not a successful review')
    return dict(status='REVIEW_DECISION_RECORDED', decision=values['decision'],
        assessment_sha256=hashlib.sha256(assessment_raw).hexdigest(), decision_sha256=hashlib.sha256(raw).hexdigest(),
        reviewer_identity_authenticated=False, campaign_advance_allowed=False, motion_authorized=False)


def export_qualification_decisions(root, records):
    """Export exact reviewed originals, not redacted summaries or new approvals."""
    from .physical_onboarding_durability import contained_path, read_bounded_regular_file
    if type(records) is not tuple or not 0 < len(records) <= 16:
        raise ValueError('One to sixteen host-selected review receipts required')
    blobs, associations = {}, []
    for operation_id, receipt in records:
        if type(operation_id) is not str or not re.fullmatch(r'operation-[a-f0-9]{32}', operation_id):
            raise ValueError('Exact retained review identity required')
        prefix = operation_id+'-first-motion-qualification-'
        originals = {}
        for name, limit in (('assessment',128*1024), ('decision',16384)):
            raw = read_bounded_regular_file(contained_path(root, prefix+name+'.json', label='qualification original'), maximum_bytes=limit)
            digest = hashlib.sha256(raw).hexdigest()
            if digest != receipt[name+'_sha256']:
                raise ValueError('Qualification original differs from its retained receipt')
            originals[name] = raw
            blobs[digest] = dict(bytes=len(raw), base64_chunks=[base64.b64encode(raw[i:i+32768]).decode('ascii')
                for i in range(0,len(raw),32768)])
        decision = decode_diagnostic_json(originals['decision'], maximum=16384)
        if decision_original(originals['assessment'], decision['reported_review'],
                recorded_ns=decision['recorded_monotonic_ns']) != originals['decision']:
            raise ValueError('Qualification decision declarations changed')
        associations.append(dict(operation_id=operation_id, assessment_sha256=receipt['assessment_sha256'],
                                 decision_sha256=receipt['decision_sha256']))
    raw = canonical(dict(schema='rocell.first_motion_qualification_export.v1', originals=blobs,
        associations=associations, motion_authorized=False, campaign_advance_allowed=False,
        reviewer_identity_authenticated=False))
    if len(raw) > 900*1024:
        raise ValueError('Complete review originals exceed export budget; no truncation allowed')
    return raw
