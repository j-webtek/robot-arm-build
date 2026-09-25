"""Supervisor orchestration with an incapable fake backend, never hardware.

Prelaunch authentication is exercised separately; here a recording stub isolates
the supervisor sequencing and real durable child-claim/IPC association checks.
"""
from dataclasses import replace
import hashlib
import json
import os
from threading import Event

import pytest

from rocell.application.first_motion_contract import FirstMotionRequest,canonical
from rocell.application.first_motion_worker_claim import reserve_first_motion_launch,claim_first_motion_worker
from rocell.providers.windows import first_motion_prelaunch as prelaunch
from rocell.providers.windows import owned_worker_process as supervisor
from rocell.providers.windows.first_motion_native_protocol import decode_request
from rocell.providers.windows.first_motion_native_result import encode_result
from test_first_motion_native_registration import registration


@pytest.mark.parametrize('fault',[None,'second-check','wrong-pid'])
def test_owned_handoff_checks_and_receipt(tmp_path,monkeypatch,fault):
    reg,outer=registration(tmp_path)
    payload=json.loads(outer.payload_json)
    request=FirstMotionRequest(canonical(payload['first_motion_request']))
    reviews=b'synthetic-claim-binding-only'
    (tmp_path/(outer.attempt_id+'-first-motion-reviews.json')).write_bytes(reviews)
    runtime_sha=hashlib.sha256(canonical(payload['registration'])).hexdigest()
    launch=reserve_first_motion_launch(tmp_path,request,runtime_original=canonical(payload['registration']),
        review_bundle_sha256=hashlib.sha256(reviews).hexdigest(),now_ns=2_000_000_000)
    payload['launch_sha256']=launch
    outer=replace(outer,payload_json=canonical(payload))
    events=[]
    def verify(*a,**kw):
        events.append('prelaunch')
        if fault=='second-check' and events.count('prelaunch')==2:
            raise ValueError('Synthetic evidence changed before resume')
    monkeypatch.setattr(prelaunch,'verify_reserved_first_motion_entry',verify)
    monkeypatch.setattr(supervisor.time,'monotonic_ns',lambda:2_000_000_000)
    class Backend:
        pid=os.getpid()+(1 if fault=='wrong-pid' else 0)
        created=resumed=tree_exited=False
        returncode=0
        stdout=stderr=b''
        written=peak_handles=peak_processes=0
        def pin(self,reg): events.append('pin')
        def start(self,reg,raw,*,check):
            check()
            events.append('start')
            self.created=self.resumed=True
            claim=claim_first_motion_worker(tmp_path,request,launch_sha256=launch,
                current_source_sha256=outer.source_sha256,current_runtime_sha256=runtime_sha,now_ns=2_000_000_000)
            life=dict(schema='rocell.first_motion_connection_lifecycle.v1',phase='CLOSED',
                request_sha256=request.request_sha256,connection_id=outer.attempt_id,
                owned_handle_count=0,pending_io_count=0,confirmed_write_bytes=0,
                read_calls={'baseline':0,'post':0},read_bytes={'baseline':0,'post':0},physical_stop_verified=False)
            execution=dict(schema='rocell.native_first_motion_execution.v1',request_sha256=request.request_sha256,
                status='CANCELLED_BEFORE_OPEN',trial=None,lifecycle=life,errors=[],
                physical_movement_verified=False,physical_stop_verified=False,replay_allowed=False)
            self.stdout=encode_result(dict(schema='rocell.first_motion_native_child_result.v1',
                claim_sha256=claim.claim_sha256,execution=execution,physical_authority=False),decode_request(raw))
        def poll(self,budget):
            self.tree_exited=True
            return True
        def cleanup(self,deadline): events.append('cleanup'); return ()
    def authorize(*args): events.append('authorize')
    worker=supervisor.OwnedWindowsWorker(reg,authorizer=authorize,_backend_factory=Backend,
        _clock=lambda:2_000_000_000)
    result=worker.run(outer,cancellation=Event(),deadline_ns=outer.expires_at_ns)
    if fault=='second-check':
        assert events==['prelaunch','pin','authorize','prelaunch','cleanup']
        assert not result.process_created and not result.initial_thread_resumed
    else:
        assert events==['prelaunch','pin','authorize','prelaunch','start','cleanup']
        assert result.process_created and result.tree_exit_confirmed
    assert result.status==('SUCCEEDED' if fault is None else 'FAILED')
    # SUCCEEDED means IPC/process success; this child reports cancellation before open.
    if fault is None:
        assert json.loads(result.stdout)['child_result']['execution']['status']=='CANCELLED_BEFORE_OPEN'
    with pytest.raises(ValueError): worker.run(outer,cancellation=Event(),deadline_ns=outer.expires_at_ns)
