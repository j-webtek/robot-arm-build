"""Wizard orchestration uses an incapable supervisor stub; no device access."""

from threading import Event
import pytest
from rocell.application import wizard_endpoint_coordinator as module
from rocell.providers.windows.owned_worker_process import OwnedWorkerResult,owned_request_wire
from test_endpoint_worker_preparation import setup


@pytest.mark.parametrize('mode',['normal','cancel-after-run','publication-failure'])
def test_failed_child_output_reaches_assigned_export_folder(tmp_path,monkeypatch,mode):
    workspace,req,kwargs = setup(tmp_path,monkeypatch)
    exports = tmp_path/'exports'
    exports.mkdir()
    calls = []
    class IncapableWorker:
        def __init__(self,reg,*,authorizer): self.reg,self.authorizer=reg,authorizer
        def run(self,outer,*,cancellation,deadline_ns):
            _,digest = owned_request_wire(self.reg,outer,deadline_ns=deadline_ns)
            self.authorizer(self.reg,outer,digest)
            calls.append('one-run')
            if mode=='cancel-after-run': cancellation.set()
            return OwnedWorkerResult('FAILED','WORKER_EXIT_FAILED',(),digest,outer.attempt_id,
                True,True,True,1,10,0,1,1,b'invalid output retained',b'failure details',
                owned_process_id=123,finished_monotonic_ns=2_000_000_000)
    monkeypatch.setattr(module,'OwnedWindowsWorker',IncapableWorker)
    if mode=='publication-failure':
        def fail_publication(*a,**k): raise OSError('Synthetic disk failure')
        monkeypatch.setattr(module,'publish_supervised_endpoint_result',fail_publication)
    outcome = module.run_reviewed_endpoint(workspace,req,**kwargs,export_root=exports,
        cancellation=Event(),check_current=lambda:None)
    assert calls==['one-run']
    if mode=='publication-failure':
        assert outcome.stage=='RETENTION_FAILED' and outcome.report_path is None
        assert outcome.owned.stdout==b'invalid output retained'
        return
    assert outcome.stage=='RETAINED'
    assert outcome.report_path.parent==exports and outcome.report_path.exists()
    assert outcome.report['status']=='RESULT_REJECTED'
    assert outcome.owned.stdout==b'invalid output retained'


@pytest.mark.parametrize('refusal',['cancel','current'])
def test_refused_parent_does_not_prepare_or_run(tmp_path,monkeypatch,refusal):
    workspace,req,kwargs = setup(tmp_path,monkeypatch)
    event = Event()
    if refusal=='cancel': event.set()
    def check():
        if refusal=='current': raise ValueError('No current operator approval')
    monkeypatch.setattr(module,'prepare_endpoint_worker',lambda *a,**k:pytest.fail('No prepare after refusal'))
    outcome = module.run_reviewed_endpoint(workspace,req,**kwargs,export_root=tmp_path,
        cancellation=event,check_current=check)
    assert outcome.stage=='PREPARATION_FAILED' and outcome.owned is None
