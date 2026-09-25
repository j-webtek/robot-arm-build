import json
import os
import pytest
from test_wrist_correction_trial_execution import fixture
from test_wrist_correction_native_result import request_bytes
from rocell.application.first_motion_contract import canonical
from rocell.providers.windows.wrist_correction_trial_execution import _execute_claimed_correction_trial
from rocell.providers.windows.wrist_correction_native_result import encode_result
from rocell.providers.windows.wrist_correction_native_protocol import digest
from rocell.providers.windows.wrist_correction_parent_review import review_correction_child_result


def run(tmp_path,monkeypatch,bias=.87,cancel=False):
    payload,permit,api,kwargs,kernel=fixture(tmp_path,monkeypatch,bias=bias)
    start=kwargs['clock_ns']()
    if cancel: kwargs['cancellation'].set()
    child=_execute_claimed_correction_trial(payload,permit,api,**kwargs)
    request=request_bytes(payload)
    raw=encode_result(child,request_raw=request)
    args=dict(request_raw=request,assigned_root=tmp_path,authority=permit._binding._reader._authority,
        owned_process_id=os.getpid(),process_started_ns=start,process_finished_ns=kwargs['clock_ns']())
    return raw,args,kernel


@pytest.mark.parametrize('bias,status',[(.87,'REPORTED_SETTLED'),(0,'WRIST_EXCURSION')])
def test_parent_reconstructs_success_and_miss_without_writes(tmp_path,monkeypatch,bias,status):
    raw,args,kernel=run(tmp_path,monkeypatch,bias)
    before={p.name:p.read_bytes() for p in tmp_path.iterdir()}
    result=review_correction_child_result(raw,**args)
    assert result['status']==status and result['reported_endpoint_reconstructed']
    assert not result['campaign_advance_allowed'] and not result['physical_accuracy_verified']
    assert before=={p.name:p.read_bytes() for p in tmp_path.iterdir()}
    assert len(kernel.writes)==1


def test_cancelled_trial_stays_incomplete(tmp_path,monkeypatch):
    raw,args,kernel=run(tmp_path,monkeypatch,cancel=True)
    result=review_correction_child_result(raw,**args)
    assert result['status']=='HELD_INCOMPLETE_RESULT' and not result['reported_endpoint_reconstructed']
    assert not kernel.writes


@pytest.mark.parametrize('fault',['status','counter','capture','publication','authority','final_counter','final_capture','final_owner'])
def test_rehashed_child_summary_still_requires_semantic_evidence(tmp_path,monkeypatch,fault):
    raw,args,_=run(tmp_path,monkeypatch)
    reference=json.loads(raw);path=tmp_path/reference['outcome']['file'];outcome=json.loads(path.read_bytes())
    if fault=='status': outcome['status']='TARGET_MISSED'
    if fault=='counter': outcome['lifecycle']['read_calls']['post']+=1
    if fault=='capture': outcome['capture_envelopes']['post']['read_calls']+=1
    if fault=='publication': outcome['publication']['report']['endpoint']['status']='TARGET_MISSED'
    if fault=='authority': outcome['motion_authorized']=True
    if fault=='final_counter': outcome['lifecycle']['read_calls']['baseline']-=outcome['capture_envelopes']['final']['capture']['read_calls']
    if fault=='final_capture': outcome['capture_envelopes']['final']['capture']['read_calls']+=1
    if fault=='final_owner': outcome['trial']['final_readback']['owner_pid']+=1
    changed=canonical(outcome);path.write_bytes(changed)
    reference['outcome'].update(bytes=len(changed),sha256=digest(changed))
    with pytest.raises(ValueError): review_correction_child_result(canonical(reference),**args)
