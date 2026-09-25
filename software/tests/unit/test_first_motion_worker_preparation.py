"""Actual package/snapshot/launch preparation with explicitly synthetic approvals."""
import hashlib
import json
from pathlib import Path

import pytest

from rocell.application import first_motion_worker_preparation as module
from rocell.application.first_motion_contract import FirstMotionRequest,canonical
from rocell.application.endpoint_reference_reader import source_fingerprint,import_build_snapshot
from rocell.safety.first_motion_review_authority import FirstMotionReviewAuthority,OPERATOR_CHECKS
from test_first_motion_reference_reader import prepare
from test_first_motion_measurement_binding import SESSION,OPERATION
from test_first_motion_review_authority import originals
from test_endpoint_current_context import fixture as context_fixture


def setup(tmp_path,monkeypatch):
    workspace=Path(__file__).resolve().parents[3]
    source=source_fingerprint(workspace)
    request=prepare(tmp_path,source,import_build_snapshot(workspace).snapshot_hash)
    data=request.to_dict()
    _,_,_,binding=context_fixture()
    native=canonical(binding.to_dict())
    data['references']['native_controller_review_sha256']=hashlib.sha256(native).hexdigest()
    (tmp_path/(data['attempt_id']+'-native_controller_review_sha256.original.json')).write_bytes(native)
    measurement_path=tmp_path/(OPERATION+'-first-motion-measurement-original.json')
    measurement=json.loads(measurement_path.read_bytes())
    measurement['source_sha256']=source
    raw=canonical(measurement)
    measurement_path.write_bytes(raw)
    (tmp_path/(data['attempt_id']+'-independent_posture_review_sha256.original.json')).write_bytes(raw)
    data['references']['independent_posture_review_sha256']=hashlib.sha256(raw).hexdigest()
    request=FirstMotionRequest(canonical(data))
    authority=FirstMotionReviewAuthority(b'a'*32)
    reviews=originals(request)
    for name in OPERATOR_CHECKS:
        row=json.loads(reviews[name]); row['recorded_ns']=2_000_000_000
        row['expires_ns']=32_000_000_000; reviews[name]=canonical(row)
    (tmp_path/(data['attempt_id']+'-first-motion-reviews.json')).write_bytes(authority.seal(request,reviews,now_ns=2_000_000_000))
    monkeypatch.setattr(module,'load_host_first_motion_review_authority',lambda _:authority)
    return workspace,request,dict(review_root=tmp_path,session_id=SESSION,
        measurement_operation_id=OPERATION,clock_ns=lambda:2_000_000_000)


def test_exact_preparation_reserves_launch_without_claim_or_open(tmp_path,monkeypatch):
    workspace,request,kwargs=setup(tmp_path,monkeypatch)
    prepared=module.prepare_first_motion_worker(workspace,request,**kwargs)
    assert len(prepared.registration.package_files)==3
    assert prepared.request.operation_sha256==request.request_sha256
    assert len(list(tmp_path.glob('*-first_motion-worker-launch.json')))==1
    assert not list(tmp_path.glob('*-worker-claimed.json'))
    assert not list(tmp_path.glob('*-first-motion-reserved.json'))
    with pytest.raises(Exception): module.prepare_first_motion_worker(workspace,request,**kwargs)


@pytest.mark.parametrize('fault',['reviews','measurement','time'])
def test_bad_or_expired_evidence_refused(tmp_path,monkeypatch,fault):
    workspace,request,kwargs=setup(tmp_path,monkeypatch)
    if fault=='reviews': (tmp_path/(request.to_dict()['attempt_id']+'-first-motion-reviews.json')).write_bytes(b'{}')
    if fault=='measurement': (tmp_path/(OPERATION+'-first-motion-measurement-original.json')).write_bytes(b'{}')
    if fault=='time': kwargs['clock_ns']=lambda:6_000_000_000
    with pytest.raises(ValueError): module.prepare_first_motion_worker(workspace,request,**kwargs)
    assert not list(tmp_path.glob('*-first-motion-native-child'))


def test_prepared_authenticated_request_reaches_only_fake_backend(tmp_path,monkeypatch):
    from threading import Event
    from rocell.providers.windows import first_motion_prelaunch,owned_worker_process as supervisor
    workspace,request,kwargs=setup(tmp_path,monkeypatch)
    monkeypatch.setattr(first_motion_prelaunch,'load_host_first_motion_review_authority',module.load_host_first_motion_review_authority)
    prepared=module.prepare_first_motion_worker(workspace,request,**kwargs)
    monkeypatch.setattr(supervisor.time,'monotonic_ns',lambda:2_000_000_000)
    calls=[]
    class Backend:
        pid=123
        created=resumed=tree_exited=False
        returncode=1
        stdout=b'synthetic backend stopped without device access'
        stderr=b''
        written=peak_handles=peak_processes=0
        def pin(self,reg): calls.append('pin')
        def start(self,reg,wire,*,check):
            check(); calls.append('start'); self.created=self.resumed=True
        def poll(self,budget): self.tree_exited=True; return True
        def cleanup(self,deadline): calls.append('cleanup'); return ()
    def authorize(*args): calls.append('authorize')
    worker=supervisor.OwnedWindowsWorker(prepared.registration,authorizer=authorize,
        _backend_factory=Backend,_clock=lambda:2_000_000_000)
    result=worker.run(prepared.request,cancellation=Event(),deadline_ns=prepared.request.expires_at_ns)
    assert calls==['pin','authorize','start','cleanup']
    assert result.status=='FAILED' and result.primary_error=='WORKER_EXIT_FAILED'
    assert result.cleanup_errors==() and result.stdout==Backend.stdout
