from dataclasses import replace
from threading import Event
import pytest
from test_wrist_correction_worker_preparation import fixture
from test_wrist_correction_review_authority import setup
from test_wrist_correction_parent_retention import inputs as failed_inputs
from rocell.application import wizard_wrist_correction_coordinator as coordinator
from rocell.providers.windows import bench_review_key
from rocell.providers.windows.owned_worker_process import owned_request_wire


def test_confirm_uses_original_acceptance_and_fixed_evidence(tmp_path,monkeypatch):
    workspace,staged,request,_,originals=fixture(tmp_path,monkeypatch)
    _,_,review,_=setup();body=request.to_dict()
    args=dict(session_id=body['session_id'],usb_identity=body['usb_identity'],originals=originals,
        operator_id='fixture',checks=review['checks'],accepted_ns=body['issued_ns'])
    confirmed,plan=coordinator.confirm_correction_run(workspace,staged,now_ns=2_000_000_000,**args)
    bench_review_key.load_host_wrist_correction_review_authority(workspace).verify_plan(plan,
        context=confirmed.to_dict(),originals=originals,now_ns=2_000_000_000,expected_basis='RETAINED_PHYSICAL_CAPTURE')
    with pytest.raises(ValueError): coordinator.confirm_correction_run(workspace,staged,now_ns=5_000_000_000,**args)


def test_attempted_run_exports_even_if_cancelled_after_run(tmp_path,monkeypatch):
    workspace,staged,request,plan,originals=fixture(tmp_path,monkeypatch)
    _,failed=failed_inputs(tmp_path);cancel=Event();seen=[]
    class FakeOwner:
        def __init__(self,registration,*,authorizer,_clock): self.reg=registration;self.authorize=authorizer
        def run(self,outer,*,cancellation,deadline_ns):
            wire,digest=owned_request_wire(self.reg,outer,deadline_ns=deadline_ns)
            self.authorize(self.reg,outer,digest);seen.append(True);cancellation.set()
            return replace(failed,request_sha256=digest,attempt_id=outer.attempt_id,stdin_bytes_written=len(wire))
    monkeypatch.setattr(coordinator,'OwnedWindowsWorker',FakeOwner)
    exports=tmp_path/'exports';exports.mkdir()
    outcome=coordinator.run_reviewed_correction(workspace,staged,request,plan_original=plan,originals=originals,
        export_root=exports,cancellation=cancel,check_current=lambda:None,clock_ns=lambda:2_000_000_000)
    assert outcome.stage=='EXPORTED',outcome
    assert len(seen)==1 and outcome.owned.primary_error=='TIMED_OUT' and outcome.report_path.is_file()
    assert not outcome.report['replay_allowed']


def test_current_context_refusal_precedes_preparation(tmp_path,monkeypatch):
    workspace,staged,request,plan,originals=fixture(tmp_path,monkeypatch)
    monkeypatch.setattr(coordinator,'OwnedWindowsWorker',lambda *args,**kwargs:pytest.fail('must not construct worker'))
    outcome=coordinator.run_reviewed_correction(workspace,staged,request,plan_original=plan,originals=originals,
        export_root=tmp_path,cancellation=Event(),check_current=lambda:False,clock_ns=lambda:2_000_000_000)
    assert outcome.stage=='PREPARATION_FAILED' and outcome.owned is None
