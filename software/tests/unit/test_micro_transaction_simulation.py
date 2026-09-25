"""Real staged durable latch plus synthetic predecessor and response fixtures."""
import base64
import hashlib
import json
import math
import pytest
from test_micro_command_admission import setup
from rocell.application.micro_transaction_simulation import run_simulated_transaction
from rocell.application.micro_endpoint_review import JOINTS


def sample(time,roll=1.25):
    pose=dict.fromkeys(JOINTS,0);pose['r']=math.radians(roll)
    raw=json.dumps(dict(T=1051,x=0,y=0,z=0,tit=0,**pose)).encode()
    return dict(status='SUCCEEDED',response_base64=base64.b64encode(raw).decode(),
                response_sha256=hashlib.sha256(raw).hexdigest(),response_bytes=len(raw),
                joints_rad=pose,request_started_monotonic_s=time-.01,
                response_finished_monotonic_s=time)


def inputs():
    return dict(now_ns=1_400_000_000,samples=[sample(t) for t in (1.85,2.35,2.85,3.35,3.75)],
                hold=dict(schema='rocell.arm_wifi_observation.v4',status='SUCCEEDED',
                          samples=[sample(4.1+i*.5) for i in range(69)]))


def test_complete_transaction_exports_and_never_sends_native(tmp_path,monkeypatch):
    admission=setup(tmp_path,monkeypatch);exports=[]
    result=run_simulated_transaction(admission,export=exports.append,**inputs())
    assert result['status']=='EXPERIMENT_VERIFIED'
    assert result['simulated_send_attempts']==1 and result['native_sends']==0
    assert result['export_succeeded'] and len(exports)==1
    assert not result['motion_authorized']
    again=run_simulated_transaction(admission,export=exports.append,**inputs())
    assert again['status']=='STOPPED' and again['simulated_send_attempts']==0


@pytest.mark.parametrize('case,reason,sends',[
    ('expiry','EXPIRED_BEFORE_SEND',0),('send','COMMAND_OUTCOME_UNCERTAIN',1),
    ('slow_receipt','COMMAND_OUTCOME_UNCERTAIN',1),
    ('missing','FEEDBACK_GAP_EXCEEDED',1),('feedback_fault','TRANSPORT_FAULT',1),
    ('corrupt','EVIDENCE_OR_OPERATION_FAILED',1),('hold_fault','HOLD_INCOMPLETE',1),
    ('hold_drift','HOLD_NOT_VERIFIED',1),('cancel','EVIDENCE_OR_OPERATION_FAILED',0)])
def test_failures_export_without_retry(tmp_path,monkeypatch,case,reason,sends):
    admission=setup(tmp_path,monkeypatch);data=inputs();exports=[]
    if case=='expiry':data['consume_elapsed_ns']=900_000_000
    if case=='send':data['send_fault']=True
    if case=='slow_receipt':data['receipt_latency_ns']=800_000_001
    if case=='missing':data['samples']=[]
    if case=='feedback_fault':data['samples'].append(dict(status='FAILED',response_finished_monotonic_s=3.8))
    if case=='corrupt':data['samples'][0]['response_sha256']='0'*64
    if case=='hold_fault':data['hold']['status']='FAILED'
    if case=='hold_drift':data['hold']['samples'][-1]=sample(38.1,1.3)
    if case=='cancel':data['cancelled']=True
    result=run_simulated_transaction(admission,export=exports.append,**data)
    assert result['status']=='STOPPED' and result['reason']==reason
    assert result['simulated_send_attempts']==sends and len(exports)==1
    assert not result['automatic_retry_allowed']


def test_export_failure_keeps_report_but_does_not_claim_success(tmp_path,monkeypatch):
    admission=setup(tmp_path,monkeypatch)
    def fail(report):raise OSError('private text')
    result=run_simulated_transaction(admission,export=fail,**inputs())
    assert result['reason']=='EXPORT_FAILED' and not result['export_succeeded']
    assert result['endpoint']['reported_settled']
    assert 'private text' not in str(result)


def test_admission_storage_failure_prevents_virtual_send(tmp_path,monkeypatch):
    admission=setup(tmp_path,monkeypatch)
    from rocell.safety import micro_command_admission as module
    def fail(*args,**kwargs):raise OSError('disk unavailable')
    monkeypatch.setattr(module,'publish_reservation_bytes',fail)
    result=run_simulated_transaction(admission,export=lambda r:None,**inputs())
    assert result['simulated_send_attempts']==0 and result['status']=='STOPPED'


def test_unchanged_verified_experiment_is_not_accuracy_success(tmp_path,monkeypatch):
    admission=setup(tmp_path,monkeypatch);data=inputs()
    angle=math.degrees(.0245)
    data['samples']=[sample(t,angle) for t in (1.85,2.35,2.85,3.35,3.75)]
    data['hold']['samples']=[sample(4.1+i*.5,angle) for i in range(69)]
    result=run_simulated_transaction(admission,export=lambda r:None,**data)
    assert result['status']=='EXPERIMENT_VERIFIED'
    assert result['reason']=='UNCHANGED_OR_SUBRESOLUTION'
    assert not result['endpoint']['desired_band_met']


def test_other_process_cannot_consume_staged_intent(tmp_path,monkeypatch):
    admission=setup(tmp_path,monkeypatch)
    from rocell.safety import micro_command_admission as module
    monkeypatch.setattr(module.os,'getpid',lambda:admission._pid+1)
    result=run_simulated_transaction(admission,export=lambda r:None,**inputs())
    assert result['status']=='STOPPED' and result['simulated_send_attempts']==0
