"""Explicit synthetic review decisions cannot grant movement authority."""
import json
import pytest
from rocell.application.first_motion_contract import canonical
from rocell.application.first_motion_qualification_decision import REVIEW_CHECKS, decision_original, record_qualification_decision


def assessment(held=False):
    return canonical(dict(schema='rocell.first_motion_qualification_assessment.v1',
        status='HELD' if held else 'READY_FOR_EXPLICIT_QUALIFICATION_REVIEW',
        holds=['SYNTHETIC_HOLD'] if held else [], physical_movement_verified=False,
        physical_accuracy_verified=False, physical_stop_verified=False, campaign_advance_allowed=False))


def values(decision):
    return dict.fromkeys(REVIEW_CHECKS, True) | dict(reviewer_id='synthetic', decision=decision, rationale='Synthetic review only.')


@pytest.mark.parametrize('decision', ['UNKNOWN','REJECT','ACCEPT_FUNCTIONAL_RESPONSE'])
@pytest.mark.parametrize('held', [False, True])
def test_decision_cannot_override_assessment(tmp_path, decision, held):
    raw = assessment(held)
    kwargs = dict(root=tmp_path, operation_id='operation-'+'1'*32, recorded_ns=100, revalidate=lambda:raw)
    if held and decision == 'ACCEPT_FUNCTIONAL_RESPONSE':
        with pytest.raises(ValueError): record_qualification_decision(raw, values(decision), **kwargs)
        assert not list(tmp_path.iterdir())
    else:
        report = record_qualification_decision(raw, values(decision), **kwargs)
        assert report['decision'] == decision
        assert not report['motion_authorized'] and not report['campaign_advance_allowed']
        with pytest.raises(Exception): record_qualification_decision(raw, values(decision), **kwargs)


@pytest.mark.parametrize('fault', ['false_check','integer_check','extra','missing_rationale','invalid_reviewer'])
def test_incomplete_or_malformed_acceptance_rejected(fault):
    inputs = values('ACCEPT_FUNCTIONAL_RESPONSE')
    if fault == 'false_check': inputs[sorted(REVIEW_CHECKS)[0]] = False
    if fault == 'integer_check': inputs[sorted(REVIEW_CHECKS)[0]] = 1
    if fault == 'extra': inputs['motion_authorized'] = True
    if fault == 'missing_rationale': inputs['rationale'] = ' '
    if fault == 'invalid_reviewer': inputs['reviewer_id'] = '../reviewer'
    with pytest.raises(ValueError): decision_original(assessment(), inputs, recorded_ns=100)


@pytest.mark.parametrize('after_publication', [False, True])
def test_revalidation_drift_never_returns_success(tmp_path, after_publication):
    calls = []
    raw = assessment()
    def revalidate():
        calls.append(True)
        return raw if after_publication and len(calls) == 1 else assessment(True)
    with pytest.raises(ValueError):
        record_qualification_decision(raw, values('ACCEPT_FUNCTIONAL_RESPONSE'), root=tmp_path,
            operation_id='operation-'+'2'*32, recorded_ns=100, revalidate=revalidate)
    assert bool(list(tmp_path.iterdir())) == after_publication


def test_export_revalidates_exact_originals_and_deduplicates(tmp_path):
    import hashlib
    from rocell.application.first_motion_qualification_decision import export_qualification_decisions
    raw = assessment()
    records = []
    for i, choice in enumerate(('UNKNOWN', 'ACCEPT_FUNCTIONAL_RESPONSE')):
        op = 'operation-'+format(i, '032x')
        report = record_qualification_decision(raw, values(choice), root=tmp_path,
            operation_id=op, recorded_ns=100+i, revalidate=lambda:raw)
        records.append((op,report))
    bundle = json.loads(export_qualification_decisions(tmp_path, tuple(records)))
    assert len(bundle['originals']) == 3
    op, report = records[1]
    path = tmp_path/(op+'-first-motion-qualification-decision.json')
    changed = path.read_bytes().replace(b'"motion_authorized":false', b'"motion_authorized":true')
    path.write_bytes(changed)
    # Even updating a claimed digest cannot turn modified flags into a valid review.
    report['decision_sha256'] = hashlib.sha256(changed).hexdigest()
    with pytest.raises(ValueError): export_qualification_decisions(tmp_path, tuple(records))
