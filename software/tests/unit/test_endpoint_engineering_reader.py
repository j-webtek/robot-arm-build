"""Synthetic decisions through the real draft coordinator, no native worker."""

import base64
import json
import pytest

from rocell.application.endpoint_engineering_review import (
    EngineeringDraftReviewReader, ENGINEERING_DRAFT_CHECKS,
)
from rocell.application.endpoint_trial_contract import _canonical
from rocell.application import wizard_endpoint_coordinator as coordinator
from test_wizard_endpoint_draft_launch import setup


def records(draft, **change):
    return tuple(_canonical(dict({
        'schema':'rocell.engineering_draft_review.v1',
        'draft_sha256':draft.draft_sha256, 'check':check,
        'actor_id':'synthetic-reviewer', 'decision':'APPROVED',
        'detail':'Synthetic only, no actual hardware review.',
        'recorded_ns':500_000_000, 'expires_ns':20_000_000_000,
    }, **change)) for check in sorted(ENGINEERING_DRAFT_CHECKS))


def test_all_five_pre_request_originals_reach_authenticated_coordinator(tmp_path,monkeypatch):
    workspace,draft,kwargs,calls = setup(tmp_path,monkeypatch)
    raw = records(draft)
    reader = EngineeringDraftReviewReader(raw,clock_ns=kwargs['clock_ns'])
    kwargs['engineering_reader'] = reader
    result = coordinator.run_endpoint_draft(workspace,draft,**kwargs)
    assert result.stage == 'TEST_NO_NATIVE_WORKER'
    assert len(calls) == 1
    bundle = json.loads(next(tmp_path.glob('*-bench-reviews.json')).read_bytes())
    retained = []
    for check in sorted(ENGINEERING_DRAFT_CHECKS):
        binding = json.loads(base64.b64decode(bundle['originals'][check]))
        retained.append(base64.b64decode(binding['draft_review_b64']))
        assert binding['request_sha256'] == calls[0].request_sha256
        assert binding['recorded_ns'] == 1_000_000_000
    assert tuple(retained) == raw
    with pytest.raises(ValueError): reader(calls[0])


@pytest.mark.parametrize('change', [
    {'decision':'DENIED'}, {'decision':'UNKNOWN'},
    {'draft_sha256':'f'*64}, {'expires_ns':900_000_000},
])
def test_invalid_originals_stop_before_bundle_and_worker(tmp_path,monkeypatch,change):
    workspace,draft,kwargs,calls = setup(tmp_path,monkeypatch)
    reader = EngineeringDraftReviewReader(records(draft,**change),clock_ns=kwargs['clock_ns'])
    kwargs['engineering_reader'] = reader
    result = coordinator.run_endpoint_draft(workspace,draft,**kwargs)
    assert result.stage == 'REVIEW_ISSUANCE_FAILED'
    assert not calls and not list(tmp_path.glob('*-bench-reviews.json'))
    assert len(list(tmp_path.glob('*-endpoint-draft-request.json'))) == 1
    # Even a failed binding cannot be invoked again to generate new timestamps.
    with pytest.raises(ValueError,match='consumed'): reader(None)


@pytest.mark.parametrize('fault', ['missing','duplicate','mixed_draft','mutable'])
def test_incomplete_or_mixed_collection_rejected(tmp_path,monkeypatch,fault):
    _,draft,_,_ = setup(tmp_path,monkeypatch)
    raw = records(draft)
    if fault == 'missing': raw = raw[:-1]
    if fault == 'duplicate': raw = raw[:-1]+(raw[0],)
    if fault == 'mixed_draft': raw = raw[:-1]+records(draft,draft_sha256='f'*64)[-1:]
    if fault == 'mutable': raw = list(raw)
    with pytest.raises(ValueError): EngineeringDraftReviewReader(raw)


def test_concurrent_calls_cannot_create_two_bindings():
    from concurrent.futures import ThreadPoolExecutor
    from rocell.application.endpoint_trial_draft import EndpointTrialDraft
    from test_endpoint_trial_contract import request
    req = request()
    reader = EngineeringDraftReviewReader(records(EndpointTrialDraft.from_request(req)),
        clock_ns=lambda:1_000_000_000)
    def invoke():
        try:
            return reader(req)
        except ValueError:
            return None
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _:invoke(),range(2)))
    assert sum(result is not None for result in results) == 1
