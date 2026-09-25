"""Draft-to-review integration with real signed files, no native worker."""

from pathlib import Path
from threading import Event

import pytest

from rocell.application import wizard_endpoint_coordinator as module
from rocell.application import bench_review_issuance
from rocell.application.endpoint_trial_draft import EndpointTrialDraft
from rocell.application.endpoint_reference_reader import (
    ORIGINAL_REFERENCES, source_fingerprint, import_build_snapshot,
)
from rocell.safety.bench_review_authority import (
    BenchReviewAuthority, BenchReviewCurrentContext, OPERATOR_CHECKS,
)
from test_endpoint_reference_reader import prepare
from test_bench_review_authority import originals


def setup(tmp_path, monkeypatch):
    workspace = Path(__file__).resolve().parents[3]
    request = prepare(tmp_path,source_fingerprint(workspace),
                      import_build_snapshot(workspace).snapshot_hash)
    body = request.to_dict()
    retained = {name:(tmp_path/(body['attempt_id']+'-'+name+'.original.json')).read_bytes()
                for name in ORIGINAL_REFERENCES}
    authority = BenchReviewAuthority(b'synthetic-draft-launch-test-key!!')
    monkeypatch.setattr(bench_review_issuance,'load_host_bench_review_authority',lambda _:authority)
    calls = []
    def runner(workspace, req, **kwargs):
        raw = (tmp_path/(req.to_dict()['attempt_id']+'-bench-reviews.json')).read_bytes()
        evidence = authority.verify(req,raw,connection_id='owned-test',
            current_references=tuple(sorted(req.to_dict()['references'].items())),
            now_ns=1_000_000_000)
        assert evidence.request_sha256==req.request_sha256
        assert req.request_sha256!=request.request_sha256
        calls.append(req)
        return module.EndpointRunOutcome('TEST_NO_NATIVE_WORKER',None,None,None,None)
    monkeypatch.setattr(module,'run_reviewed_endpoint',runner)
    draft = EndpointTrialDraft.from_request(request)
    kwargs = dict(expected_draft_sha256=draft.draft_sha256,
        attempt_id='operation-'+'c'*32,reference_originals=retained,
        review_root=tmp_path,export_root=tmp_path,session_id='wizard-'+'d'*32,
        connection_id='owned-test',
        operator_reader=lambda r:{k:v for k,v in originals(r).items() if k in OPERATOR_CHECKS},
        engineering_reader=lambda r:{k:v for k,v in originals(r).items() if k not in OPERATOR_CHECKS},
        context_factory=lambda r:lambda:BenchReviewCurrentContext('owned-test',
            (0x10c4,0xea60,'A'*32),tuple(sorted(r.to_dict()['references'].items())),1_000_000_000),
        cancellation=Event(),check_current=lambda:None,clock_ns=lambda:1_000_000_000)
    return workspace,draft,kwargs,calls


def test_real_review_issuance_reaches_existing_runner_once(tmp_path,monkeypatch):
    workspace,draft,kwargs,calls = setup(tmp_path,monkeypatch)
    result = module.run_endpoint_draft(workspace,draft,**kwargs)
    assert result.stage=='TEST_NO_NATIVE_WORKER'
    assert len(calls)==1
    again = module.run_endpoint_draft(workspace,draft,**kwargs)
    assert again.stage=='DRAFT_RESERVATION_FAILED'
    assert len(calls)==1


def test_parent_deadline_is_not_renewed(tmp_path,monkeypatch):
    workspace,draft,kwargs,calls = setup(tmp_path,monkeypatch)
    result = module.run_endpoint_draft(workspace,draft,deadline_ns=29_000_000_000,**kwargs)
    assert result.stage=='TEST_NO_NATIVE_WORKER'
    assert calls[0].to_dict()['deadline_monotonic_ns']==29_000_000_000


@pytest.mark.parametrize('deadline',[True,1_000_000_000,10_000_000_000])
def test_invalid_or_insufficient_deadline_never_reserves(tmp_path,monkeypatch,deadline):
    workspace,draft,kwargs,calls = setup(tmp_path,monkeypatch)
    result = module.run_endpoint_draft(workspace,draft,deadline_ns=deadline,**kwargs)
    assert result.stage=='DRAFT_VALIDATION_FAILED'
    assert not calls
    assert not list(tmp_path.glob('*-endpoint-draft-request.json'))


@pytest.mark.parametrize('fault',['changed_draft','original','cancelled','engineering'])
def test_refusals_never_dispatch(tmp_path,monkeypatch,fault):
    workspace,draft,kwargs,calls = setup(tmp_path,monkeypatch)
    if fault=='changed_draft': kwargs['expected_draft_sha256']='f'*64
    if fault=='original': kwargs['reference_originals']['configuration_sha256']=b'{"changed":true}'
    if fault=='cancelled': kwargs['cancellation'].set()
    if fault=='engineering': kwargs['engineering_reader']=lambda r:{}
    result = module.run_endpoint_draft(workspace,draft,**kwargs)
    assert result.stage.endswith('_FAILED')
    assert not calls
    reserved = list(tmp_path.glob('*-endpoint-draft-request.json'))
    assert bool(reserved)==(fault=='engineering')


def test_cancel_after_staging_retains_request_without_reviews(tmp_path,monkeypatch):
    workspace,draft,kwargs,calls = setup(tmp_path,monkeypatch)
    count = [0]
    def current():
        count[0]+=1
        if count[0]==2: raise ValueError('Operator no longer present')
    kwargs['check_current']=current
    result = module.run_endpoint_draft(workspace,draft,**kwargs)
    assert result.stage=='REFERENCE_STAGING_FAILED'
    assert list(tmp_path.glob('*-endpoint-draft-request.json'))
    assert not list(tmp_path.glob('*-bench-reviews.json'))
    assert not calls


@pytest.mark.parametrize('delay_stage', ['staging', 'review'])
def test_review_delay_preserves_deadline_and_never_reaches_worker(tmp_path,monkeypatch,delay_stage):
    import json
    workspace,draft,kwargs,calls = setup(tmp_path,monkeypatch)
    tick = [1_000_000_000]
    kwargs['clock_ns'] = lambda:tick[0]
    kwargs['context_factory'] = lambda r:lambda:BenchReviewCurrentContext('owned-test',
        (0x10c4,0xea60,'A'*32),tuple(sorted(r.to_dict()['references'].items())),tick[0])
    if delay_stage == 'staging':
        checks = [0]
        def current():
            checks[0] += 1
            if checks[0] == 2: tick[0] += 4_000_000_000
        kwargs['check_current'] = current
    else:
        reader = kwargs['engineering_reader']
        def delayed(r):
            tick[0] += 4_000_000_000
            return reader(r)
        kwargs['engineering_reader'] = delayed
    result = module.run_endpoint_draft(workspace,draft,**kwargs)
    assert result.stage == 'REVIEW_BUDGET_FAILED'
    assert not calls
    reserved = list(tmp_path.glob('*-endpoint-draft-request.json'))
    assert len(reserved) == 1
    body = json.loads(reserved[0].read_bytes())
    assert body['issued_monotonic_ns'] == 1_000_000_000
    assert body['deadline_monotonic_ns'] == 31_000_000_000
    # A bundle already issued before detecting the exhausted reserve is retained
    # for diagnosis, never treated as permission for a shorter or renewed run.
    assert bool(list(tmp_path.glob('*-bench-reviews.json'))) == (delay_stage == 'review')


def test_draft_through_real_preparation_and_failure_export(tmp_path,monkeypatch):
    from test_endpoint_worker_preparation import setup as prepare_fixture
    from rocell.application import endpoint_worker_preparation
    from rocell.providers.windows.owned_worker_process import OwnedWorkerResult, owned_request_wire
    workspace,request,_ = prepare_fixture(tmp_path,monkeypatch)
    authority = endpoint_worker_preparation.load_host_bench_review_authority(workspace)
    monkeypatch.setattr(bench_review_issuance,'load_host_bench_review_authority',lambda _:authority)
    draft = EndpointTrialDraft.from_request(request)
    body = request.to_dict()
    retained = {name:(tmp_path/(body['attempt_id']+'-'+name+'.original.json')).read_bytes()
                for name in ORIGINAL_REFERENCES}
    calls = []
    class IncapableWorker:
        def __init__(self,reg,*,authorizer): self.reg,self.authorizer=reg,authorizer
        def run(self,outer,*,cancellation,deadline_ns):
            _,digest = owned_request_wire(self.reg,outer,deadline_ns=deadline_ns)
            self.authorizer(self.reg,outer,digest)
            calls.append(outer.attempt_id)
            return OwnedWorkerResult('FAILED','WORKER_EXIT_FAILED',(),digest,outer.attempt_id,
                True,True,True,1,10,0,1,1,b'synthetic failed child',b'test diagnostic',
                owned_process_id=123,finished_monotonic_ns=2_000_000_000)
    monkeypatch.setattr(module,'OwnedWindowsWorker',IncapableWorker)
    result = module.run_endpoint_draft(workspace,draft,
        expected_draft_sha256=draft.draft_sha256,attempt_id='operation-'+'c'*32,
        reference_originals=retained,review_root=tmp_path,export_root=tmp_path,
        session_id='wizard-'+'d'*32,connection_id='operation-'+'c'*32,
        operator_reader=lambda r:{k:v for k,v in originals(r).items() if k in OPERATOR_CHECKS},
        engineering_reader=lambda r:{k:v for k,v in originals(r).items() if k not in OPERATOR_CHECKS},
        context_factory=lambda r:lambda:BenchReviewCurrentContext('operation-'+'c'*32,
            (0x10c4,0xea60,'A'*32),tuple(sorted(r.to_dict()['references'].items())),1_000_000_000),
        cancellation=Event(),check_current=lambda:None,clock_ns=lambda:1_000_000_000)
    assert calls==['operation-'+'c'*32]
    assert result.stage=='RETAINED'
    assert result.report['status']=='RESULT_REJECTED'
    assert result.report_path.exists()
    assert result.owned.stdout==b'synthetic failed child'
    assert list(tmp_path.glob('*-endpoint-worker-launch.json'))
