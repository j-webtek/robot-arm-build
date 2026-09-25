"""Synthetic runtime/review records; never start a native worker or hardware."""
import hashlib
import os

import pytest

from rocell.application import first_motion_worker_claim as module
from rocell.application.endpoint_worker_claim import claim_endpoint_worker
from test_first_motion_admission import setup


def prepared(tmp_path):
    request,_,clock,path = setup(tmp_path)
    runtime = b'{"worker":"synthetic-commissioning-only"}'
    launch = module.reserve_first_motion_launch(tmp_path,request,runtime_original=runtime,
        review_bundle_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),now_ns=clock[0])
    args = dict(launch_sha256=launch,current_source_sha256=request.to_dict()['references']['source_sha256'],
        current_runtime_sha256=hashlib.sha256(runtime).hexdigest(),now_ns=clock[0])
    return request,args,path


def test_exact_process_claim_consumed_once_and_receipt_verified(tmp_path):
    request,args,_ = prepared(tmp_path)
    claim = module.claim_first_motion_worker(tmp_path,request,**args)
    consume = {k:v for k,v in args.items() if k!='launch_sha256'}
    claim.consume(request,**consume)
    with pytest.raises(ValueError): claim.consume(request,**consume)
    with pytest.raises(Exception): module.claim_first_motion_worker(tmp_path,request,**args)
    receipt = module.verify_first_motion_worker_receipt(tmp_path,request,
        claim_sha256=claim.claim_sha256,launch_sha256=args['launch_sha256'],
        owned_process_id=os.getpid(),runtime_sha256=args['current_runtime_sha256'],finished_ns=args['now_ns']+1)
    assert not receipt['physical_authority'] and not receipt['replay_allowed']
    with pytest.raises(ValueError): claim_endpoint_worker(tmp_path,request,**args)


@pytest.mark.parametrize('field',['launch_sha256','current_source_sha256','current_runtime_sha256'])
def test_changed_context_never_claimed(tmp_path,field):
    request,args,_ = prepared(tmp_path)
    args[field]='f'*64
    with pytest.raises(ValueError): module.claim_first_motion_worker(tmp_path,request,**args)
    assert not list(tmp_path.glob('*-first_motion-worker-claimed.json'))


def test_review_changes_after_reservation_refused(tmp_path):
    request,args,path = prepared(tmp_path)
    path.write_bytes(b'{}')
    with pytest.raises(ValueError): module.claim_first_motion_worker(tmp_path,request,**args)


def test_process_identity_change_burns_consumption(tmp_path,monkeypatch):
    request,args,_ = prepared(tmp_path)
    claim = module.claim_first_motion_worker(tmp_path,request,**args)
    pid = os.getpid()
    consume = {k:v for k,v in args.items() if k!='launch_sha256'}
    monkeypatch.setattr(module.os,'getpid',lambda:pid+1)
    with pytest.raises(ValueError): claim.consume(request,**consume)
    monkeypatch.setattr(module.os,'getpid',lambda:pid)
    with pytest.raises(ValueError): claim.consume(request,**consume)


def test_interrupted_claim_cannot_be_reclaimed(tmp_path,monkeypatch):
    request,args,_ = prepared(tmp_path)
    original = module.publish_reservation_bytes
    def crash(checkpoint):
        if checkpoint=='publication.after_temp_create': raise RuntimeError('synthetic interruption')
    monkeypatch.setattr(module,'publish_reservation_bytes',lambda *a,**kw:original(*a,**kw,fault_injector=crash))
    with pytest.raises(RuntimeError): module.claim_first_motion_worker(tmp_path,request,**args)
    monkeypatch.setattr(module,'publish_reservation_bytes',original)
    with pytest.raises(Exception): module.claim_first_motion_worker(tmp_path,request,**args)
