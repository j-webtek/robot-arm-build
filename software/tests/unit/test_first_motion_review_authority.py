"""Synthetic authentication checks do not attest real measurements or operators."""
import base64
import json

import pytest

from rocell.application.first_motion_contract import FirstMotionRequest, canonical
from rocell.safety.bench_review_authority import BenchReviewAuthority
from rocell.safety.first_motion_review_authority import (
    FirstMotionReviewAuthority, FirstMotionReviewEvidence,
    REQUIRED_CHECKS, ENGINEERING_CHECKS,
)
from test_first_motion_contract import request
from test_endpoint_trial_contract import request as endpoint_request


def originals(r):
    return {name:canonical({'schema':'rocell.first_motion_review.v1',
        'scope':'ONE_WRIST_RESPONSE_EXPERIMENT','check':name,'actor_id':'synthetic-reviewer',
        'decision':'APPROVED','evidence_kind':'ENGINEERING_SELECTION_REVIEW' if name in ENGINEERING_CHECKS else 'EXACT_REQUEST_OPERATOR_ATTESTATION',
        'binding_sha256':r.selection_sha256 if name in ENGINEERING_CHECKS else r.request_sha256,
        'recorded_ns':500_000_000 if name in ENGINEERING_CHECKS else 1_000_000_000,
        'expires_ns':300_500_000_000 if name in ENGINEERING_CHECKS else 31_000_000_000,
        'detail':'Synthetic test only; no physical review performed.'}) for name in REQUIRED_CHECKS}


def verify(authority,r,raw,**kwargs):
    args=dict(connection_id=r.to_dict()['attempt_id'],
              current_references=tuple(sorted(r.to_dict()['references'].items())),now_ns=1_000_000_000)
    args.update(kwargs)
    return authority.verify(r,raw,**args)


def test_derived_authority_roundtrips_originals_without_renewal():
    r=request(); reviews=originals(r)
    authority=BenchReviewAuthority(b'a'*32).for_first_motion()
    assert type(authority) is FirstMotionReviewAuthority
    raw=authority.seal(r,reviews,now_ns=1_000_000_000)
    evidence=verify(authority,r,raw)
    assert type(evidence) is FirstMotionReviewEvidence
    assert evidence.expires_at_ns==31_000_000_000
    assert len(evidence.checks)==12
    assert not hasattr(evidence,'consume')
    body=json.loads(raw)
    assert {k:base64.b64decode(v) for k,v in body['originals'].items()}==reviews


@pytest.mark.parametrize('change',[
    {'decision':'UNKNOWN'},{'decision':'DENIED'},{'scope':'ONE_NONCONTACT_BENCH_ENDPOINT'},
    {'recorded_ns':True},{'recorded_ns':1_000_000_001},{'expires_ns':1_000_000_000},
    {'binding_sha256':'f'*64},{'detail':''},{'actor_id':'../bad'},{'extra':True},
])
def test_invalid_original_is_never_promoted_to_approval(change):
    r=request(); reviews=originals(r); name='operator_present'
    value=json.loads(reviews[name]); value.update(change); reviews[name]=canonical(value)
    with pytest.raises(ValueError):
        FirstMotionReviewAuthority(b'a'*32).seal(r,reviews,now_ns=1_000_000_000)


def test_operator_cannot_use_old_engineering_window_or_later_expiry():
    r=request()
    for name,change in [('operator_present',{'recorded_ns':500_000_000}),
        ('operator_present',{'expires_ns':32_000_000_000}),
        ('independent_starting_geometry_review',{'expires_ns':301_000_000_000})]:
        reviews=originals(r); value=json.loads(reviews[name]); value.update(change); reviews[name]=canonical(value)
        with pytest.raises(ValueError):
            FirstMotionReviewAuthority(b'a'*32).seal(r,reviews,now_ns=1_000_000_000)


def test_missing_checks_unknown_key_changed_context_and_expiry_fail():
    r=request(); authority=FirstMotionReviewAuthority(b'a'*32); reviews=originals(r)
    raw=authority.seal(r,reviews,now_ns=1_000_000_000)
    for kwargs in ({'connection_id':'COM7'},{'connection_id':'operation-'+'c'*32},
                   {'current_references':()},{'now_ns':31_000_000_000}):
        with pytest.raises(ValueError): verify(authority,r,raw,**kwargs)
    with pytest.raises(ValueError): verify(FirstMotionReviewAuthority(b'b'*32),r,raw)
    reviews.pop('operator_present')
    with pytest.raises(ValueError): authority.seal(r,reviews,now_ns=1_000_000_000)


def test_endpoint_and_commissioning_types_and_bundles_are_disjoint():
    r=request(); parent=BenchReviewAuthority(b'a'*32); authority=parent.for_first_motion()
    raw=authority.seal(r,originals(r),now_ns=1_000_000_000)
    with pytest.raises(ValueError):
        parent.seal(r,originals(r),now_ns=1_000_000_000)
    with pytest.raises(ValueError):
        parent.verify(endpoint_request(),raw,connection_id='test',current_references=(),now_ns=1_000_000_000)
    with pytest.raises(ValueError):
        authority.seal(endpoint_request(),originals(r),now_ns=1_000_000_000)
    with pytest.raises(ValueError):
        verify(FirstMotionReviewAuthority(b'a'*32),r,raw)  # Derived key differs from parent key.


def test_engineering_selection_is_stable_only_across_envelope_fields():
    r=request(); changed=r.to_dict(); changed['attempt_id']='operation-'+'c'*32
    other=FirstMotionRequest(canonical(changed))
    assert other.selection_sha256==r.selection_sha256
    assert other.request_sha256!=r.request_sha256
    with pytest.raises(ValueError):
        FirstMotionReviewAuthority(b'a'*32).seal(other,originals(r),now_ns=1_000_000_000)
    changed['references']['source_sha256']='c'*64
    assert FirstMotionRequest(canonical(changed)).selection_sha256!=r.selection_sha256


def test_tampered_bundle_is_rejected():
    r=request(); authority=FirstMotionReviewAuthority(b'a'*32)
    body=json.loads(authority.seal(r,originals(r),now_ns=1_000_000_000))
    body['originals']['operator_present']=base64.b64encode(b'{}').decode()
    with pytest.raises(ValueError): verify(authority,r,canonical(body))


def test_host_loader_derives_without_provisioning_or_exporting_key(monkeypatch,tmp_path):
    from rocell.providers.windows import bench_review_key
    calls=[]
    def load(workspace):
        calls.append(workspace)
        return BenchReviewAuthority(b'a'*32)
    monkeypatch.setattr(bench_review_key,'load_host_bench_review_authority',load)
    authority=bench_review_key.load_host_first_motion_review_authority(tmp_path)
    assert calls==[tmp_path]
    assert type(authority) is FirstMotionReviewAuthority
    r=request(); raw=authority.seal(r,originals(r),now_ns=1_000_000_000)
    assert verify(BenchReviewAuthority(b'a'*32).for_first_motion(),r,raw).request_sha256==r.request_sha256
