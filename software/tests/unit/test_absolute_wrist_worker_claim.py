"""Durable process association tests; no executable qualification or device IO."""
import hashlib
import json
import os
import subprocess
import sys

import pytest

from rocell.application.first_motion_contract import canonical
from rocell.application.physical_onboarding_durability import (
    publish_reservation_bytes, PhysicalOnboardingDurabilityError,
)
from rocell.application.absolute_wrist_worker_claim import (
    reserve_absolute_wrist_launch, claim_absolute_wrist_worker, verify_absolute_wrist_worker_receipt,
)
from rocell.safety.absolute_wrist_review_authority import AbsoluteWristIntent
from test_absolute_wrist_review_authority import intent


def fixture(tmp_path):
    body = intent()
    runtime = canonical({'synthetic': 'not an executable approval'})
    body['references']['runtime_sha256'] = hashlib.sha256(runtime).hexdigest()
    request = AbsoluteWristIntent(canonical(body))
    review = b'{"synthetic":"storage fixture, not authenticated review"}'
    publish_reservation_bytes(tmp_path, body['attempt_id']+'-absolute-wrist-reviews.json',
                              review, maximum_bytes=8192)
    launch = reserve_absolute_wrist_launch(tmp_path, request, runtime_original=runtime,
        review_bundle_sha256=hashlib.sha256(review).hexdigest(), now_ns=1_000_000_001)
    kwargs = dict(launch_sha256=launch, current_source_sha256=body['references']['source_sha256'],
                  current_runtime_sha256=body['references']['runtime_sha256'], now_ns=1_000_000_002)
    return request, kwargs, runtime, review


def consume_kwargs(kwargs):
    return {k: v for k, v in kwargs.items() if k != 'launch_sha256'}


def test_claim_once_no_restart_and_receipt_after_exit_time(tmp_path):
    request, kwargs, runtime, review = fixture(tmp_path)
    claim = claim_absolute_wrist_worker(tmp_path, request, **kwargs)
    claim.consume(request, **consume_kwargs(kwargs))
    with pytest.raises(ValueError): claim.consume(request, **consume_kwargs(kwargs))
    with pytest.raises((FileExistsError, PhysicalOnboardingDurabilityError)):
        claim_absolute_wrist_worker(tmp_path, request, **kwargs)
    with pytest.raises((FileExistsError, PhysicalOnboardingDurabilityError)):
        reserve_absolute_wrist_launch(tmp_path, request, runtime_original=runtime,
            review_bundle_sha256=hashlib.sha256(review).hexdigest(), now_ns=1_000_000_003)
    result = verify_absolute_wrist_worker_receipt(tmp_path, request,
        claim_sha256=claim.claim_sha256, launch_sha256=kwargs['launch_sha256'],
        owned_process_id=os.getpid(), runtime_sha256=kwargs['current_runtime_sha256'], finished_ns=40_000_000_000)
    assert not result['replay_allowed'] and not result['physical_authority']


@pytest.mark.parametrize('fault', ['source', 'runtime', 'review', 'launch', 'claimed', 'pid', 'expired'])
def test_changed_context_burns_claim(tmp_path, monkeypatch, fault):
    request, kwargs, _, _ = fixture(tmp_path)
    claim = claim_absolute_wrist_worker(tmp_path, request, **kwargs)
    consume = consume_kwargs(kwargs)
    if fault in ('source', 'runtime'): consume['current_'+fault+'_sha256'] = 'f'*64
    if fault == 'expired': consume['now_ns'] = 21_000_000_000
    if fault in ('review', 'launch', 'claimed'):
        suffix = 'reviews' if fault == 'review' else fault
        (tmp_path/(request.to_dict()['attempt_id']+'-absolute-wrist-'+suffix+'.json')).write_bytes(b'{}')
    if fault == 'pid': monkeypatch.setattr(os, 'getpid', lambda: -1)
    with pytest.raises(ValueError): claim.consume(request, **consume)
    with pytest.raises(ValueError): claim.consume(request, **consume)


@pytest.mark.parametrize('fault', ['pid', 'claim_hash', 'finish', 'runtime'])
def test_parent_receipt_requires_exact_observed_association(tmp_path, fault):
    request, kwargs, _, _ = fixture(tmp_path)
    claim = claim_absolute_wrist_worker(tmp_path, request, **kwargs)
    receipt = dict(claim_sha256=claim.claim_sha256, launch_sha256=kwargs['launch_sha256'],
        owned_process_id=os.getpid(), runtime_sha256=kwargs['current_runtime_sha256'], finished_ns=2_000_000_000)
    if fault == 'pid': receipt['owned_process_id'] += 1
    if fault == 'claim_hash': receipt['claim_sha256'] = 'f'*64
    if fault == 'finish': receipt['finished_ns'] = 1
    if fault == 'runtime': receipt['runtime_sha256'] = 'f'*64
    with pytest.raises(ValueError): verify_absolute_wrist_worker_receipt(tmp_path, request, **receipt)


def test_real_child_exit_leaves_claim_nonreplayable(tmp_path):
    request, kwargs, _, _ = fixture(tmp_path)
    script = '''import json,sys,os
from pathlib import Path
from rocell.application.first_motion_contract import canonical
from rocell.safety.absolute_wrist_review_authority import AbsoluteWristIntent
from rocell.application.absolute_wrist_worker_claim import claim_absolute_wrist_worker
v=json.loads(sys.stdin.read())
c=claim_absolute_wrist_worker(Path(v['root']),AbsoluteWristIntent(canonical(v['intent'])),**v['kwargs'])
print(json.dumps(dict(pid=os.getpid(),claim_sha256=c.claim_sha256)))
'''
    child = subprocess.run([sys.executable, '-I', '-c', script],
        input=canonical(dict(root=str(tmp_path), intent=request.to_dict(), kwargs=kwargs)),
        capture_output=True, timeout=15, check=True)
    receipt = json.loads(child.stdout)
    assert receipt['pid'] != os.getpid()
    verified = verify_absolute_wrist_worker_receipt(tmp_path, request,
        claim_sha256=receipt['claim_sha256'], launch_sha256=kwargs['launch_sha256'],
        owned_process_id=receipt['pid'], runtime_sha256=kwargs['current_runtime_sha256'], finished_ns=2_000_000_000)
    assert not verified['replay_allowed']
    with pytest.raises((FileExistsError, PhysicalOnboardingDurabilityError)):
        claim_absolute_wrist_worker(tmp_path, request, **kwargs)
