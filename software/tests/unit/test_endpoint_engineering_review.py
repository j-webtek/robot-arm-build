"""Synthetic draft decisions; never evidence of actual engineering approval."""

import base64
import pytest

from rocell.application.endpoint_engineering_review import EngineeringDraftReview
from rocell.application.endpoint_trial_draft import EndpointTrialDraft
from rocell.application.endpoint_trial_contract import EndpointTrialRequest, _canonical
from rocell.safety.bench_review_authority import BenchReviewAuthority
from test_endpoint_trial_contract import request
from test_bench_review_authority import originals


def draft_review(req, **changes):
    value = dict(schema='rocell.engineering_draft_review.v1',
        draft_sha256=EndpointTrialDraft.from_request(req).draft_sha256,
        check='noncontact_route_review',actor_id='synthetic-reviewer',decision='APPROVED',
        detail='Synthetic fixture only, no physical approval.',
        recorded_ns=500_000_000,expires_ns=20_000_000_000)
    value.update(changes)
    return EngineeringDraftReview(_canonical(value))


def test_original_time_and_bytes_survive_authenticated_request_binding():
    req = request()
    review = draft_review(req)
    records = originals(req)
    records['noncontact_route_review'] = review.bind_request(req,now_ns=1_000_000_000)
    import json
    bound = json.loads(records['noncontact_route_review'])
    assert base64.b64decode(bound['draft_review_b64']) == review.canonical_bytes
    assert review.to_dict()['recorded_ns'] == 500_000_000
    assert bound['recorded_ns'] == 1_000_000_000
    authority = BenchReviewAuthority(b'synthetic-engineering-test-key-12')
    raw = authority.seal(req,records,now_ns=1_000_000_000)
    result = authority.verify(req,raw,connection_id='test',
        current_references=tuple(sorted(req.to_dict()['references'].items())),now_ns=1_000_000_000)
    assert result.expires_at_ns == 20_000_000_000


@pytest.mark.parametrize('decision', ['DENIED','UNKNOWN'])
def test_nonapproval_cannot_bind(decision):
    req = request()
    with pytest.raises(ValueError): draft_review(req,decision=decision).bind_request(req,now_ns=1_000_000_000)


def test_changed_reference_requires_new_engineering_review():
    req = request()
    body = req.to_dict()
    body['references']['baseline_qualification_sha256'] = 'b'*64
    changed = EndpointTrialRequest(_canonical(body))
    with pytest.raises(ValueError): draft_review(req).bind_request(changed,now_ns=1_000_000_000)


@pytest.mark.parametrize('change', [
    {'check':'operator_present'}, {'recorded_ns':True}, {'expires_ns':True},
    {'expires_ns':301_000_000_000}, {'detail':''}, {'decision':True},
])
def test_invalid_or_operator_draft_rejected(change):
    with pytest.raises(ValueError): draft_review(request(),**change)


def test_expired_original_cannot_be_refreshed():
    req = request()
    with pytest.raises(ValueError):
        draft_review(req,expires_ns=900_000_000).bind_request(req,now_ns=1_000_000_000)


@pytest.mark.parametrize('mutation', ['operator','actor','expiry','wrong_original'])
def test_authority_rechecks_nested_original_not_just_outer_claim(mutation):
    import json
    req = request()
    records = originals(req)
    review = draft_review(req,expires_ns=15_000_000_000)
    value = json.loads(review.bind_request(req,now_ns=1_000_000_000))
    check = 'noncontact_route_review'
    if mutation == 'operator':
        check = 'operator_present'
        value['check'] = check
    if mutation == 'actor': value['actor_id'] = 'different-actor'
    if mutation == 'expiry': value['expires_ns'] = 20_000_000_000
    if mutation == 'wrong_original':
        value['draft_review_b64'] = base64.b64encode(
            draft_review(req,draft_sha256='f'*64).canonical_bytes).decode('ascii')
    records[check] = _canonical(value)
    with pytest.raises(ValueError):
        BenchReviewAuthority(b'synthetic-engineering-test-key-12').seal(req,records,now_ns=1_000_000_000)
