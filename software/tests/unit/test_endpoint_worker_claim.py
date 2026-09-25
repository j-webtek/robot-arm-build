"""Durable endpoint worker claiming with synthetic registrations and reviews."""

from concurrent.futures import ProcessPoolExecutor
import hashlib
import multiprocessing
import os

import pytest

from rocell.application import endpoint_worker_claim as module
from rocell.application.physical_onboarding_durability import publish_bytes, PublicationMode
from test_bench_review_authority import fixture
from test_endpoint_trial_contract import request


def prepared(tmp_path):
    req,authority,records,raw,filename,reader,tick,current = fixture(tmp_path)
    runtime = b'{"worker":"synthetic-test-only"}'
    launch = module.reserve_endpoint_launch(tmp_path,req,runtime_original=runtime,
        review_bundle_sha256=hashlib.sha256(raw).hexdigest(),now_ns=tick[0])
    args = dict(launch_sha256=launch,current_source_sha256=req.to_dict()['references']['source_sha256'],
                current_runtime_sha256=hashlib.sha256(runtime).hexdigest(),now_ns=tick[0])
    return req,args,filename


def test_claim_consumption_is_exact_one_use(tmp_path):
    req,args,_ = prepared(tmp_path)
    claim = module.claim_endpoint_worker(tmp_path,req,**args)
    consume = {k:v for k,v in args.items() if k!='launch_sha256'}
    claim.consume(req,**consume)
    with pytest.raises(ValueError): claim.consume(req,**consume)
    with pytest.raises(Exception): module.claim_endpoint_worker(tmp_path,req,**args)


@pytest.mark.parametrize('field', ['launch_sha256','current_source_sha256','current_runtime_sha256'])
def test_mismatched_context_does_not_claim(tmp_path,field):
    req,args,_ = prepared(tmp_path)
    args[field] = 'f'*64
    with pytest.raises(ValueError): module.claim_endpoint_worker(tmp_path,req,**args)
    assert not list(tmp_path.glob('*-endpoint-worker-claimed.json'))


def test_changed_review_bundle_refused(tmp_path):
    req,args,filename = prepared(tmp_path)
    publish_bytes(tmp_path,filename,b'{}',mode=PublicationMode.REPLACE)
    with pytest.raises(ValueError): module.claim_endpoint_worker(tmp_path,req,**args)


def test_claim_cannot_be_consumed_in_another_process(tmp_path,monkeypatch):
    req,args,_ = prepared(tmp_path)
    claim = module.claim_endpoint_worker(tmp_path,req,**args)
    pid = os.getpid()
    monkeypatch.setattr(module.os,'getpid',lambda:pid+1)
    with pytest.raises(ValueError):
        claim.consume(req,**{k:v for k,v in args.items() if k!='launch_sha256'})


def test_partial_claim_after_interruption_prevents_retry(tmp_path,monkeypatch):
    req,args,_ = prepared(tmp_path)
    original = module.publish_reservation_bytes
    def crash(checkpoint):
        if checkpoint=='publication.after_temp_create': raise RuntimeError('injected interruption')
    monkeypatch.setattr(module,'publish_reservation_bytes',lambda *a,**kw:original(*a,**kw,fault_injector=crash))
    with pytest.raises(RuntimeError): module.claim_endpoint_worker(tmp_path,req,**args)
    assert next(tmp_path.glob('*-endpoint-worker-claimed.json')).stat().st_size==0
    monkeypatch.setattr(module,'publish_reservation_bytes',original)
    with pytest.raises(Exception): module.claim_endpoint_worker(tmp_path,req,**args)


def _child_claim(task):
    root,args = task
    try:
        module.claim_endpoint_worker(root,request(),**args)
        return True
    except Exception:
        return False


def test_separate_processes_cannot_claim_same_launch(tmp_path):
    req,args,_ = prepared(tmp_path)
    with ProcessPoolExecutor(max_workers=2,mp_context=multiprocessing.get_context('spawn')) as pool:
        outcomes = list(pool.map(_child_claim,[(str(tmp_path),args)]*2))
    assert outcomes.count(True)==1
