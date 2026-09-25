"""Synthetic decisions test intake semantics, not physical arm readiness."""

import pytest

from rocell.application.endpoint_review_intake import EndpointReviewIntake
from rocell.application import bench_review_issuance
from rocell.safety.bench_endpoint import REQUIRED_CHECKS
from rocell.safety.bench_review_authority import BenchReviewAuthority, OPERATOR_CHECKS
from test_endpoint_trial_contract import request
from test_bench_review_issuance import prepared


def fill(intake, decision='APPROVED'):
    return {check: intake.record(check=check, actor_id='synthetic-reviewer',
        decision=decision, detail='Synthetic test decision, not hardware evidence.',
        expires_ns=20_000_000_000) for check in REQUIRED_CHECKS}


def test_intake_composes_with_existing_issuance(tmp_path, monkeypatch):
    req, kwargs, _ = prepared(tmp_path, monkeypatch)
    intake_root = tmp_path/'originals'
    intake_root.mkdir()
    intake = EndpointReviewIntake(req, root=intake_root, clock_ns=lambda:1_000_000_000)
    records = fill(intake)
    assert intake.operator_reader(req) == {k:v for k,v in records.items() if k in OPERATOR_CHECKS}
    assert intake.engineering_reader(req) == {k:v for k,v in records.items() if k not in OPERATOR_CHECKS}
    kwargs.update(operator_reader=intake.operator_reader, engineering_reader=intake.engineering_reader)
    result = bench_review_issuance.issue_bench_reviews(tmp_path, req, **kwargs)
    assert result['physical_authority'] is False
    bundle = (tmp_path/(req.to_dict()['attempt_id']+'-bench-reviews.json')).read_bytes()
    authority = BenchReviewAuthority(b'test-only-not-production-key-12345')
    assert authority.verify(req, bundle, connection_id='owned-test',
        current_references=tuple(sorted(req.to_dict()['references'].items())),
        now_ns=1_000_000_000).request_sha256 == req.request_sha256


@pytest.mark.parametrize('decision', ['DENIED', 'UNKNOWN'])
def test_refusal_retained_and_cannot_be_replaced(tmp_path, decision):
    req = request()
    intake = EndpointReviewIntake(req, root=tmp_path, clock_ns=lambda:1_000_000_000)
    fill(intake, decision)
    before = {p.name:p.read_bytes() for p in tmp_path.iterdir()}
    with pytest.raises(ValueError): intake.operator_reader(req)
    with pytest.raises(Exception): fill(intake)
    assert {p.name:p.read_bytes() for p in tmp_path.iterdir()} == before


def test_missing_decisions_not_synthesized(tmp_path):
    req = request()
    intake = EndpointReviewIntake(req, root=tmp_path, clock_ns=lambda:1_000_000_000)
    with pytest.raises(Exception): intake.operator_reader(req)
    assert list(tmp_path.iterdir()) == []


def test_expiry_not_refreshed(tmp_path):
    req = request()
    tick = [1_000_000_000]
    intake = EndpointReviewIntake(req, root=tmp_path, clock_ns=lambda:tick[0])
    fill(intake)
    tick[0] = 20_000_000_000
    with pytest.raises(ValueError): intake.engineering_reader(req)


@pytest.mark.parametrize('change', [
    {'decision':True}, {'actor_id':'../bad'}, {'detail':''},
    {'expires_ns':True}, {'expires_ns':22_000_000_000}, {'check':'../outside'},
])
def test_invalid_decision_no_publication(tmp_path, change):
    intake = EndpointReviewIntake(request(), root=tmp_path, clock_ns=lambda:1_000_000_000)
    args = dict(check='operator_present', actor_id='synthetic', decision='APPROVED',
                detail='Synthetic test only', expires_ns=20_000_000_000)
    args.update(change)
    with pytest.raises(ValueError): intake.record(**args)
    assert list(tmp_path.iterdir()) == []
