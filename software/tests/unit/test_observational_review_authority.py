import copy
import json

import pytest

from rocell.safety.bench_review_authority import BenchReviewAuthority
from rocell.safety.observational_review_authority import CHECKS, REFERENCES, validate_intent
from rocell.application.first_motion_contract import canonical


def intent():
    return dict(schema='rocell.observational_intent.v1', session_id='wizard-'+'1'*32,
        attempt_id='operation-'+'2'*32,
        usb_identity=dict(vid=0x10c4, pid=0xea60, serial_number='A'*32),
        references=dict.fromkeys(REFERENCES, 'b'*64), issued_ns=1_000_000_000,
        deadline_ns=21_000_000_000, direction=-1,
        policy='ONE_WRIST_DEGREE_FROM_OWNED_BASELINE_SPD20_ACC1_NO_RETURN')


def review():
    return dict(operator_id='synthetic', recorded_ns=1_000_000_001,
                checks=dict.fromkeys(CHECKS, True))


def verify(authority, raw, expected=None, now=1_000_000_003):
    expected = intent() if expected is None else expected
    return authority.verify(raw, expected_intent=expected,
        current_usb_identity=expected['usb_identity'], current_references=expected['references'], now_ns=now)


def test_seals_operator_report_without_precision_measurements():
    authority = BenchReviewAuthority(b'A'*32).for_observational_motion()
    raw = authority.seal(intent(), review(), now_ns=1_000_000_002)
    result = verify(authority, raw)
    assert result['evidence_kind'] == 'HOST_AUTHENTICATED_OPERATOR_REPORT'
    assert result['motion_authorized'] is False
    assert result['physical_truth_verified'] is False
    assert set(json.loads(raw)['review']['checks']) == CHECKS


@pytest.mark.parametrize('fault', ['tamper', 'other_key', 'unit', 'source', 'attempt', 'expired'])
def test_mismatched_or_expired_context_rejected(fault):
    authority = BenchReviewAuthority(b'A'*32).for_observational_motion()
    raw = authority.seal(intent(), review(), now_ns=1_000_000_002)
    expected, now = intent(), 1_000_000_003
    if fault == 'tamper':
        body = json.loads(raw)
        body['intent']['direction'] = 1
        raw = canonical(body)
    if fault == 'other_key': authority = BenchReviewAuthority(b'B'*32).for_observational_motion()
    if fault == 'unit': expected['usb_identity']['serial_number'] = 'B'*32
    if fault == 'source': expected['references']['source_sha256'] = 'c'*64
    if fault == 'attempt': expected['attempt_id'] = 'operation-'+'3'*32
    if fault == 'expired': now = expected['deadline_ns']
    with pytest.raises(ValueError): verify(authority, raw, expected, now)


@pytest.mark.parametrize('check', sorted(CHECKS))
@pytest.mark.parametrize('value', [False, None, 1, 'yes'])
def test_no_implicit_operator_approval(check, value):
    authority = BenchReviewAuthority(b'A'*32).for_observational_motion()
    reported = review()
    reported['checks'][check] = value
    with pytest.raises(ValueError): authority.seal(intent(), reported, now_ns=1_000_000_002)


def test_policy_cannot_be_widened():
    altered = copy.deepcopy(intent())
    altered['policy'] = 'FULL_SWEEP'
    with pytest.raises(ValueError): validate_intent(altered, 1_000_000_002)
