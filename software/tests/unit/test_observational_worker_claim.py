import hashlib
import os

import pytest

from rocell.application.first_motion_contract import canonical
from rocell.application.physical_onboarding_durability import publish_reservation_bytes
from rocell.application.observational_worker_claim import (
    reserve_observational_launch, claim_observational_worker, verify_observational_worker_receipt,
)
from rocell.providers.windows.observational_native_protocol import validate_payload
from test_observational_native_protocol import wire


def fixture(tmp_path):
    payload = wire(tmp_path)['payload']
    request = validate_payload(payload)
    # Storage/claim fixture only; native admission separately authenticates reviews.
    review = b'{"synthetic":"not-an-approved-review"}'
    name = request.to_dict()['attempt_id']+'-observational-reviews.json'
    publish_reservation_bytes(tmp_path, name, review, maximum_bytes=8192)
    runtime = canonical(payload['registration'])
    launch = reserve_observational_launch(tmp_path, request, runtime_original=runtime,
        review_bundle_sha256=hashlib.sha256(review).hexdigest(), now_ns=1_000_000_001)
    kwargs = dict(launch_sha256=launch, current_source_sha256=request.to_dict()['references']['source_sha256'],
        current_runtime_sha256=request.to_dict()['references']['runtime_sha256'], now_ns=1_000_000_002)
    claim = claim_observational_worker(tmp_path, request, **kwargs)
    return request, claim, kwargs, runtime, review


def test_one_use_claim_and_owned_receipt(tmp_path):
    request, claim, kwargs, runtime, review = fixture(tmp_path)
    consume = {k:v for k,v in kwargs.items() if k != 'launch_sha256'}
    claim.consume(request, **consume)
    with pytest.raises(ValueError): claim.consume(request, **consume)
    with pytest.raises(Exception): claim_observational_worker(tmp_path, request, **kwargs)
    with pytest.raises(Exception):
        reserve_observational_launch(tmp_path, request, runtime_original=runtime,
            review_bundle_sha256=hashlib.sha256(review).hexdigest(), now_ns=1_000_000_003)
    receipt = verify_observational_worker_receipt(tmp_path, request,
        claim_sha256=claim.claim_sha256, launch_sha256=kwargs['launch_sha256'],
        owned_process_id=os.getpid(), runtime_sha256=kwargs['current_runtime_sha256'],
        finished_ns=40_000_000_000)
    assert receipt['replay_allowed'] is False


@pytest.mark.parametrize('fault', ['pid', 'source', 'runtime', 'review', 'claim', 'expired'])
def test_changed_context_burns_consumption(tmp_path, monkeypatch, fault):
    request, claim, kwargs, _, _ = fixture(tmp_path)
    consume = {k:v for k,v in kwargs.items() if k != 'launch_sha256'}
    if fault == 'pid':
        original = os.getpid()
        monkeypatch.setattr(os, 'getpid', lambda: original+1)
    if fault == 'source': consume['current_source_sha256'] = 'f'*64
    if fault == 'runtime': consume['current_runtime_sha256'] = 'f'*64
    if fault == 'expired': consume['now_ns'] = 31_000_000_000
    if fault in ('review','claim'):
        suffix = 'reviews' if fault == 'review' else 'claimed'
        (tmp_path/(request.to_dict()['attempt_id']+'-observational-'+suffix+'.json')).write_bytes(b'{}')
    with pytest.raises(ValueError): claim.consume(request, **consume)
    with pytest.raises(ValueError): claim.consume(request, **consume)


def test_parent_pid_must_match_claim(tmp_path):
    request, claim, kwargs, _, _ = fixture(tmp_path)
    with pytest.raises(ValueError):
        verify_observational_worker_receipt(tmp_path, request,
            claim_sha256=claim.claim_sha256, launch_sha256=kwargs['launch_sha256'],
            owned_process_id=os.getpid()+1, runtime_sha256=kwargs['current_runtime_sha256'],
            finished_ns=2_000_000_000)
