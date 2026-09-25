"""Fixture keys and synthetic identity only; no device or protected-key access."""
import copy
import json

import pytest

from rocell.application.first_motion_contract import canonical
from rocell.safety.absolute_wrist_review_authority import AbsoluteWristIntent, SCHEMA
from rocell.safety.bench_review_authority import BenchReviewAuthority
from rocell.safety.observational_review_authority import CHECKS, ObservationalIntent
from test_absolute_wrist_diagnostic import fixture
from test_observational_review_authority import intent as relative_intent, review


def intent():
    body = relative_intent()
    del body['direction'], body['policy']
    body['schema'] = SCHEMA
    body['draft'] = fixture()[0].to_dict()
    return body


def authority():
    return BenchReviewAuthority(b'A' * 32).for_absolute_wrist_diagnostic()


def verify(auth, raw, expected=None, **overrides):
    body = intent() if expected is None else expected
    params = dict(expected_intent=body, current_usb_identity=body['usb_identity'],
                  current_references=body['references'], now_ns=1_000_000_003)
    params.update(overrides)
    return auth.verify(raw, **params)


def test_exact_signed_target_and_start_without_native_authority():
    auth = authority()
    body = intent()
    request = AbsoluteWristIntent(canonical(body))
    raw = auth.seal(body, review(), now_ns=1_000_000_002)
    result = verify(auth, raw)
    assert result['intent_sha256'] == request.request_sha256
    assert not result['motion_authorized'] and not result['physical_truth_verified']
    assert json.loads(raw)['intent']['draft'] == body['draft']
    request.require_start_time(1_000_000_003)
    with pytest.raises(ValueError): request.require_start_time(11_000_000_001)


@pytest.mark.parametrize('fault', ['target', 'start', 'limits', 'tampered_raw',
    'key', 'identity', 'reference', 'expired', 'future', 'attempt'])
def test_changed_context_or_authentication_rejected(fault):
    auth, expected = authority(), intent()
    raw = auth.seal(expected, review(), now_ns=1_000_000_002)
    overrides = {}
    if fault == 'target': expected['draft']['target_deg'] = 4
    if fault == 'start': expected['draft']['expected_start_joints_rad']['t'] += .001
    if fault == 'limits': expected['draft']['limits']['maximum_commands'] = 2
    if fault == 'tampered_raw':
        changed = json.loads(raw)
        changed['intent']['draft']['expected_start_joints_rad']['t'] += .001
        raw = canonical(changed)
    if fault == 'key': auth = BenchReviewAuthority(b'B' * 32).for_absolute_wrist_diagnostic()
    if fault == 'identity':
        overrides['current_usb_identity'] = dict(expected['usb_identity'], serial_number='B' * 32)
    if fault == 'reference':
        overrides['current_references'] = dict(expected['references'], source_sha256='c' * 64)
    if fault == 'expired': overrides['now_ns'] = expected['deadline_ns']
    if fault == 'future': overrides['now_ns'] = expected['issued_ns'] - 1
    if fault == 'attempt': expected['attempt_id'] = 'operation-' + '9' * 32
    with pytest.raises(ValueError): verify(auth, raw, expected, **overrides)


@pytest.mark.parametrize('check', sorted(CHECKS))
@pytest.mark.parametrize('value', [False, None, 1, 'yes'])
def test_confirmation_not_inferred(check, value):
    reported = review()
    reported['checks'][check] = value
    with pytest.raises(ValueError): authority().seal(intent(), reported, now_ns=1_000_000_002)


def test_relative_and_absolute_domains_cannot_be_interchanged():
    relative = BenchReviewAuthority(b'A' * 32).for_observational_motion()
    absolute = authority()
    old = relative.seal(relative_intent(), review(), now_ns=1_000_000_002)
    new = absolute.seal(intent(), review(), now_ns=1_000_000_002)
    assert relative._key != absolute._key
    with pytest.raises(ValueError): verify(absolute, old)
    with pytest.raises(ValueError):
        relative.verify(new, expected_intent=relative_intent(),
                        current_usb_identity=relative_intent()['usb_identity'],
                        current_references=relative_intent()['references'], now_ns=1_000_000_003)
    with pytest.raises(ValueError): ObservationalIntent(canonical(intent()))
    with pytest.raises(ValueError): AbsoluteWristIntent(canonical(relative_intent()))


@pytest.mark.parametrize('fault', ['extra', 'bool_time', 'short', 'long', 'zero_hash', 'mutable'])
def test_invalid_intent_rejected(fault):
    body = copy.deepcopy(intent())
    if fault == 'extra': body['approved'] = True
    if fault == 'bool_time': body['issued_ns'] = True
    if fault == 'short': body['deadline_ns'] = body['issued_ns'] + 10_000_000_000
    if fault == 'long': body['deadline_ns'] = body['issued_ns'] + 31_000_000_000
    if fault == 'zero_hash': body['references']['source_sha256'] = '0' * 64
    raw = canonical(body)
    if fault == 'mutable': raw = bytearray(raw)
    with pytest.raises(ValueError): AbsoluteWristIntent(raw)
