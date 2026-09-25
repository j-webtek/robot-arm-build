import copy
import pytest
from test_wrist_correction_evidence_store import staged
from rocell.application import wrist_correction_worker_claim as claims
from rocell.safety.bench_review_authority import BenchReviewAuthority


def setup(tmp_path):
    payload,_,_=staged(tmp_path)
    authority=BenchReviewAuthority(b'A'*32).for_wrist_correction_review()
    now=payload['context']['issued_ns']+1_000_000_000
    payload['launch_sha256']=claims.reserve_correction_launch(payload,root=tmp_path,authority=authority,now_ns=now)
    args=dict(current_source_sha256=payload['context']['references']['source_sha256'],
        current_runtime_sha256=payload['context']['references']['runtime_sha256'],now_ns=now)
    return payload,authority,args


def test_claim_and_consumption_are_each_one_use(tmp_path):
    payload,authority,args=setup(tmp_path)
    claim=claims.claim_correction_worker(payload,root=tmp_path,authority=authority,**args)
    claim.consume(payload,**args)
    assert (tmp_path/claims._name(payload,'worker-consumed')).is_file()
    with pytest.raises(ValueError): claim.consume(payload,**args)
    with pytest.raises((RuntimeError,OSError)):
        claims.claim_correction_worker(payload,root=tmp_path,authority=authority,**args)


@pytest.mark.parametrize('fault',['plan','source','runtime','payload','pid','claim','expiry'])
def test_failed_consumption_is_sticky_before_any_io(tmp_path,monkeypatch,fault):
    payload,authority,args=setup(tmp_path)
    claim=claims.claim_correction_worker(payload,root=tmp_path,authority=authority,**args)
    bad=copy.deepcopy(payload); params=dict(args)
    if fault=='plan':
        (tmp_path/(payload['context']['attempt_id']+'-wrist-correction-plan-review.json')).write_bytes(b'{}')
    if fault=='source': params['current_source_sha256']='d'*64
    if fault=='runtime': params['current_runtime_sha256']='d'*64
    if fault=='payload': bad['plan_sha256']='d'*64
    if fault=='pid': monkeypatch.setattr(claims.os,'getpid',lambda:0)
    if fault=='claim': (tmp_path/claims._name(payload,'worker-claimed')).write_bytes(b'{}')
    if fault=='expiry': params['now_ns']=payload['context']['deadline_ns']
    with pytest.raises((ValueError,RuntimeError)): claim.consume(bad,**params)
    assert not (tmp_path/claims._name(payload,'worker-consumed')).exists()
    with pytest.raises(ValueError,match='already used'): claim.consume(payload,**args)


def test_changed_launch_rejected_before_claim(tmp_path):
    payload,authority,args=setup(tmp_path)
    (tmp_path/claims._name(payload,'launch')).write_bytes(b'{}')
    with pytest.raises(ValueError):
        claims.claim_correction_worker(payload,root=tmp_path,authority=authority,**args)
    assert not (tmp_path/claims._name(payload,'worker-claimed')).exists()


def test_competing_claims_have_one_winner(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    payload,authority,args=setup(tmp_path)
    def attempt():
        try:
            return claims.claim_correction_worker(payload,root=tmp_path,authority=authority,**args)
        except (OSError,RuntimeError):
            return None
    with ThreadPoolExecutor(max_workers=2) as pool:
        results=list(pool.map(lambda _:attempt(),range(2)))
    assert sum(value is not None for value in results)==1


def test_consumption_storage_failure_cannot_retry(tmp_path,monkeypatch):
    payload,authority,args=setup(tmp_path)
    claim=claims.claim_correction_worker(payload,root=tmp_path,authority=authority,**args)
    def fail(*args,**kwargs): raise OSError('synthetic storage failure')
    monkeypatch.setattr(claims,'publish_reservation_bytes',fail)
    with pytest.raises(OSError): claim.consume(payload,**args)
    with pytest.raises(ValueError,match='already used'): claim.consume(payload,**args)


def test_consumption_cannot_predate_process_claim(tmp_path):
    payload,authority,args=setup(tmp_path)
    later=dict(args,now_ns=args['now_ns']+1_000_000_000)
    claim=claims.claim_correction_worker(payload,root=tmp_path,authority=authority,**later)
    with pytest.raises(ValueError,match='predates'): claim.consume(payload,**args)


def receipt_fixture(tmp_path):
    payload,authority,args=setup(tmp_path)
    claim=claims.claim_correction_worker(payload,root=tmp_path,authority=authority,**args)
    claim.consume(payload,**dict(args,now_ns=args['now_ns']+100_000_000))
    receipt_args=dict(root=tmp_path,authority=authority,claim_sha256=claim.claim_sha256,
        owned_process_id=claims.os.getpid(),process_started_ns=args['now_ns'],
        process_finished_ns=args['now_ns']+1_000_000_000)
    return payload,receipt_args


def test_receipt_reconciles_records_but_does_not_prove_containment(tmp_path):
    payload,args=receipt_fixture(tmp_path)
    result=claims.verify_correction_worker_receipt(payload,**args)
    assert result['records_consistent'] and result['finished_within_deadline']
    assert not result['process_containment_verified'] and not result['endpoint_verified']
    args['process_finished_ns']=payload['context']['deadline_ns']+1
    assert not claims.verify_correction_worker_receipt(payload,**args)['finished_within_deadline']


@pytest.mark.parametrize('fault',['pid','bool_pid','start','finish','hash','missing_consumed',
    'consumed_pid','consumed_time','consumed_extra','consumed_flag','plan','root'])
def test_receipt_rejects_unmatched_process_or_records(tmp_path,fault):
    import json
    payload,args=receipt_fixture(tmp_path)
    if fault=='pid': args['owned_process_id']+=1
    if fault=='bool_pid': args['owned_process_id']=True
    if fault=='start': args['process_started_ns']+=1
    if fault=='finish': args['process_finished_ns']=args['process_started_ns']
    if fault=='hash': args['claim_sha256']='d'*64
    path=tmp_path/claims._name(payload,'worker-consumed')
    if fault=='missing_consumed': path.unlink()
    if fault.startswith('consumed_'):
        body=json.loads(path.read_bytes())
        if fault=='consumed_pid': body['pid']+=1
        if fault=='consumed_time': body['consumed_ns']=args['process_started_ns']-1
        if fault=='consumed_extra': body['approved']=True
        if fault=='consumed_flag': body['physical_authority']=True
        path.write_bytes(claims.canonical(body))
    if fault=='plan':
        (tmp_path/(payload['context']['attempt_id']+'-wrist-correction-plan-review.json')).write_bytes(b'{}')
    if fault=='root':
        other=tmp_path/'other';other.mkdir();args['root']=other
    with pytest.raises((ValueError,RuntimeError)):
        claims.verify_correction_worker_receipt(payload,**args)
