"""Contained-owner orchestration with an incapable fake backend only."""
from threading import Event
import json
import pytest
from test_wrist_correction_native_registration import fixture
from rocell.providers.windows import owned_worker_process as owner
from rocell.providers.windows import wrist_correction_prelaunch as prelaunch
from rocell.providers.windows import bench_review_key
from rocell.providers.windows.wrist_correction_native_protocol import validate_payload


class Backend:
    def __init__(self):
        self.created=self.resumed=self.tree_exited=False
        self.pid=123;self.returncode=1;self.written=0
        self.peak_handles=10;self.peak_processes=1
        self.stdout=b'partial child output';self.stderr=b'fixture failure'
        self.started=0;self.cleaned=0
    def pin(self,registration): pass
    def start(self,registration,wire,*,check):
        check();self.created=self.resumed=True;self.started+=1;self.written=len(wire)
    def poll(self,budget): self.tree_exited=True;return True
    def cleanup(self,deadline): self.cleaned+=1;return ()


def setup(tmp_path,monkeypatch):
    registration,request=fixture(tmp_path)
    checks=[]
    def verify(payload,**kwargs): checks.append(True);return validate_payload(payload)
    monkeypatch.setattr(prelaunch,'verify_reserved_correction_entry',verify)
    # No protected-key or device access in these process-owner plumbing tests.
    monkeypatch.setattr(bench_review_key,'load_host_wrist_correction_review_authority',lambda _:None)
    monkeypatch.setattr(owner.time,'monotonic_ns',lambda:2_000_000_000)
    backend=Backend()
    return registration,request,backend,checks


def test_child_failure_is_retained_after_cleanup_without_retry(tmp_path,monkeypatch):
    registration,request,backend,checks=setup(tmp_path,monkeypatch)
    authorizations=[]
    worker=owner.OwnedWindowsWorker(registration,authorizer=lambda *args:authorizations.append(True),
        _backend_factory=lambda:backend,_clock=lambda:2_000_000_000)
    result=worker.run(request,cancellation=Event(),deadline_ns=request.expires_at_ns)
    assert result.primary_error=='WORKER_EXIT_FAILED',result.to_dict()
    assert backend.started==backend.cleaned==1 and len(authorizations)==1 and len(checks)==2
    assert result.parsed_result['status']=='HELD_PROCESS_FAILURE'
    retained=tmp_path/result.parsed_result['parent_original']['file']
    assert json.loads(retained.read_bytes())['process']['primary_error']=='WORKER_EXIT_FAILED'
    with pytest.raises(ValueError): worker.run(request,cancellation=Event(),deadline_ns=request.expires_at_ns)
    assert backend.started==1


def test_authorizer_refusal_precedes_start_and_is_retained(tmp_path,monkeypatch):
    registration,request,backend,_=setup(tmp_path,monkeypatch)
    def refuse(*args): raise PermissionError('fixture refusal')
    result=owner.OwnedWindowsWorker(registration,authorizer=refuse,_backend_factory=lambda:backend,
        _clock=lambda:2_000_000_000).run(request,cancellation=Event(),deadline_ns=request.expires_at_ns)
    assert result.primary_error=='PermissionError' and backend.started==0
    assert result.parsed_result['status']=='HELD_PROCESS_FAILURE'


def test_finalization_failure_cannot_look_successful(tmp_path,monkeypatch):
    from rocell.application import wrist_correction_process_finalization as finalization
    registration,request,backend,_=setup(tmp_path,monkeypatch)
    def fail(*args,**kwargs): raise OSError('synthetic disk failure')
    monkeypatch.setattr(finalization,'finalize_correction_process',fail)
    result=owner.OwnedWindowsWorker(registration,authorizer=lambda *args:None,_backend_factory=lambda:backend,
        _clock=lambda:2_000_000_000).run(request,cancellation=Event(),deadline_ns=request.expires_at_ns)
    assert result.status=='FAILED' and result.primary_error=='WORKER_EXIT_FAILED'
    assert 'CORRECTION_FINALIZATION:OSError' in result.cleanup_errors
    assert result.parsed_result is None
