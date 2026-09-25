"""Complete claimed trial using a fake kernel; never accesses the arm."""
import ctypes
import math
from dataclasses import replace
from threading import Event
import pytest

from test_endpoint_current_context import fixture as endpoint_fixture
from test_endpoint_serial_connection import OwnerKernel
from test_wrist_correction_review_authority import setup
from rocell.application.first_motion_contract import canonical
from rocell.application.wrist_correction_worker_claim import reserve_correction_launch,claim_correction_worker
from rocell.arm.protocol import encode_line
from rocell.providers.windows import wrist_correction_native_protocol as protocol
from rocell.providers.windows.wrist_correction_evidence_store import stage_evidence
from rocell.providers.windows.wrist_correction_current_context import (
    WristCorrectionContextRequest,WristCorrectionCurrentContextReader,AuthenticatedWristCorrectionReader)
from rocell.safety.wrist_correction_admission import admit_wrist_correction
from rocell.providers.windows.wrist_correction_serial_api import WindowsWristCorrectionSerialApi
from rocell.providers.windows.nonpurging_serial_api import WindowsNativeSerialApi
from rocell.providers.windows.wrist_correction_trial_execution import _execute_claimed_correction_trial


def fixture(tmp_path,monkeypatch,*,bias=.87):
    _,snapshots,_,controller=endpoint_fixture()
    authority,ctx,review,args=setup()
    registration={'fixture':'NOT_A_LAUNCH_REGISTRATION'}
    ctx['references']['runtime_sha256']=protocol.digest(canonical(registration))
    ctx['references']['native_controller_review_sha256']=controller.binding_sha256
    ctx['deadline_ns']=ctx['issued_ns']+30_000_000_000
    clock=[2_000_000_000]
    request=WristCorrectionContextRequest(canonical(ctx))
    plan=authority.seal_plan(ctx,review,originals=args['originals'],now_ns=args['now_ns'],expected_basis=args['expected_basis'])
    payload=dict(schema=protocol.PAYLOAD_SCHEMA,root=str(tmp_path),context=ctx,registration=registration,
        launch_sha256='c'*64,review_authority_id='local-wrist-correction-review-v1',
        plan_sha256=protocol.digest(plan),originals=protocol.evidence_manifest(args['originals']),expected_basis=args['expected_basis'])
    stage_evidence(payload,assigned_root=tmp_path,originals=args['originals'],plan_raw=plan)
    payload['launch_sha256']=reserve_correction_launch(payload,root=tmp_path,authority=authority,now_ns=clock[0])
    refs=dict(current_source_sha256=ctx['references']['source_sha256'],current_runtime_sha256=ctx['references']['runtime_sha256'])
    claim=claim_correction_worker(payload,root=tmp_path,authority=authority,now_ns=clock[0],**refs)
    def metadata():
        return replace(snapshots[0],started_monotonic_ns=clock[0],finished_monotonic_ns=clock[0])
    current=WristCorrectionCurrentContextReader(request,binding=controller,connection_id=ctx['attempt_id'],
        metadata_reader=metadata,references_reader=lambda:tuple(sorted(ctx['references'].items())),clock_ns=lambda:clock[0])
    reader=AuthenticatedWristCorrectionReader(request,root=tmp_path,authority=authority,context_reader=current,
        originals=args['originals'],expected_basis=args['expected_basis'],clock_ns=lambda:clock[0])
    cancel=Event()
    permit=admit_wrist_correction(request,reader=reader,root=tmp_path,cancellation=cancel)
    kernel=OwnerKernel()
    def load(api): api._dll=kernel;return kernel
    monkeypatch.setattr(WindowsNativeSerialApi,'_load_kernel',load)
    monkeypatch.setattr(ctypes,'get_last_error',lambda:kernel.last_error,raising=False)
    api=WindowsWristCorrectionSerialApi.from_correction_permit(request,permit,
        port_name=permit._binding._port,connection_id=ctx['attempt_id'])
    joints=args['originals'][0][0].to_dict()['draft']['expected_start_joints_rad']
    kernel.input=encode_line(dict(T=1051,x=1,y=2,z=3,tit=0,**joints))
    read,write=kernel.ReadFile,kernel.WriteFile
    def timed_read(*args): clock[0]+=20_000_000;return read(*args)
    def timed_write(*args):
        clock[0]+=1_000_000
        result=write(*args)
        kernel.input=encode_line(dict(T=1051,x=1,y=2,z=3,tit=0,
            **dict(joints,t=math.radians(-.87890625+bias))))
        return result
    kernel.ReadFile,kernel.WriteFile=timed_read,timed_write
    kwargs=dict(worker_claim=claim,cancellation=cancel,clock_ns=lambda:clock[0],
        idle_wait=lambda s:clock.__setitem__(0,clock[0]+round(s*1e9)),**refs)
    return payload,permit,api,kwargs,kernel


@pytest.mark.parametrize('bias,status',[(.87,'REPORTED_SETTLED'),(0,'WRIST_EXCURSION')])
def test_claimed_trial_verifies_nominal_endpoint_once(tmp_path,monkeypatch,bias,status):
    payload,permit,api,kwargs,kernel=fixture(tmp_path,monkeypatch,bias=bias)
    result=_execute_claimed_correction_trial(payload,permit,api,**kwargs)
    assert result['status']==status,result
    assert len(kernel.writes)==1 and kernel.closed==[202,201,101]
    assert not result['owned_process_verified']
    assert result['result']['outcome_retention']['status']=='RETAINED'
    trial=result['result']['trial']
    assert trial['schema']=='rocell.wrist_correction_trial.v2'
    assert trial['write']['dispatch_checked_ns']>=trial['write']['started_ns']
    assert set(result['result']['capture_envelopes'])=={'baseline','final','post'}
    with pytest.raises(ValueError): _execute_claimed_correction_trial(payload,permit,api,**kwargs)
    assert len(kernel.writes)==1


@pytest.mark.parametrize('fault',['source','selection','cancel','context','originals'])
def test_preopen_faults_never_write(tmp_path,monkeypatch,fault):
    payload,permit,api,kwargs,kernel=fixture(tmp_path,monkeypatch)
    if fault=='source': kwargs['current_source_sha256']='d'*64
    if fault=='selection': payload['plan_sha256']='d'*64
    if fault=='context': payload['context']['attempt_id']='operation-'+'e'*32
    if fault=='originals': permit._binding._reader._originals.reverse()
    if fault=='cancel':
        kwargs['cancellation'].set()
        result=_execute_claimed_correction_trial(payload,permit,api,**kwargs)
        assert result['status']=='CANCELLED_BEFORE_OPEN'
    else:
        with pytest.raises(ValueError): _execute_claimed_correction_trial(payload,permit,api,**kwargs)
    assert not kernel.writes and not kernel.closed
