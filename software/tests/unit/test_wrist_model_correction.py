import hashlib
import json
import math
from copy import deepcopy
import pytest
from rocell.application import wrist_model_correction as module


def fixture(monkeypatch,start=3.779296882):
    context=dict.fromkeys(('native_controller_review_sha256','tool_payload_sha256',
        'workcell_sha256','protocol_review_sha256'),'same')
    model=dict(schema='rocell.offline_wrist_endpoint_models.v1',compensation_enabled=False,
        motion_authorized=False,direction_bias_deg={'INCREASING':-.439453128,'DECREASING':.966796894},
        constant_bias_deg=.263671883,provenance=[dict(report_sha256='f'*64,configuration_references=context)])
    raw=json.dumps(model).encode();entries=[];results={}
    for i in range(6):
        direction='INCREASING' if i<3 else 'DECREASING'
        error=-.330078123 if i<3 else .900390625
        entries.append(dict(directory=str(i),report_name=str(i),report_sha256=str(i)*64))
        results[str(i)]=dict(valid=True,reconstruction_consistent=True,report_sha256=str(i)*64,
            configuration_references=context.copy(),endpoint_diagnostics=[dict(leg_id='leg-01',
                target_rad=math.radians(2),final_rad=math.radians(2+error),direction=direction,
                start_rad=math.radians(.966796894 if i<3 else 3.779296882),
                signed_error_rad=math.radians(error),command=dict(T=101,joint=4,rad=math.radians(2),spd=20,acc=1))])
    monkeypatch.setattr(module,'verify_native_retained_export',lambda d,n:deepcopy(results[d]))
    args=dict(expected_model_sha256=hashlib.sha256(raw).hexdigest(),exports=entries,
        start_joints_rad=[0,0,0,math.radians(start),0,0])
    return raw,args,results


def trace(proposal, final, *, other=False):
    p=proposal.to_dict();start=p['expected_start_joints_rad'];rows=[]
    for i in range(1,251):
        joints=start.copy();joints[3]=start[3]+(math.radians(final)-start[3])*min(i/50,1)
        if other:joints[0]+=math.radians(1)
        stamp=1_000_000_000+i*20_000_000;rows.append((stamp,stamp,joints))
    return rows


@pytest.mark.parametrize('start,expected',[(3.779296882,1.033203106),(.966796894,2.439453128)])
def test_raw_command_and_nominal_are_distinct_and_not_double_quantized(monkeypatch,start,expected):
    raw,args,_=fixture(monkeypatch,start);p=module.propose_model_correction(raw,**args);body=p.to_dict()
    assert body['nominal_target_deg']==2
    assert body['proposed_command_target_deg']==pytest.approx(expected)
    assert body['proposed_command_target_rad']!=body['reference_goal']['representable_rad']
    assert not body['motion_authorized'] and not body['compensation_enabled']
    assert body['maximum_commands']==1 and not body['automatic_retry']
    body['nominal_target_deg']=99
    assert p.to_dict()['nominal_target_deg']==2


def test_arrival_at_adjusted_command_cannot_pass_nominal_target(monkeypatch):
    raw,args,_=fixture(monkeypatch);p=module.propose_model_correction(raw,**args)
    result=module.score_synthetic_correction(p,trace(p,p.to_dict()['proposed_command_target_deg']))
    assert result['command_endpoint_diagnostic']['endpoint_verified']
    assert not result['simulation_passed']
    assert not result['nominal_endpoint']['endpoint_verified']


def test_arrival_at_nominal_passes_despite_not_reaching_motor_target(monkeypatch):
    raw,args,_=fixture(monkeypatch);p=module.propose_model_correction(raw,**args)
    result=module.score_synthetic_correction(p,trace(p,2))
    assert result['simulation_passed'] and result['nominal_endpoint']['endpoint_verified']
    assert result['correction_screen_passed']
    assert not result['command_endpoint_diagnostic']['endpoint_verified']
    assert not result['automatic_next_command_allowed']


def test_within_nominal_band_is_not_necessarily_an_improved_correction(monkeypatch):
    raw,args,_=fixture(monkeypatch,.966796894);p=module.propose_model_correction(raw,**args)
    r=module.score_synthetic_correction(p,trace(p,p.to_dict()['proposed_command_target_deg']))
    assert r['simulation_passed']  # 2.439 is within the existing +/-0.5 band.
    assert not r['correction_screen_passed']  # Worse than the uncorrected 0.330 error.


@pytest.mark.parametrize('fault',['model_hash','duplicate','partial','context','prediction','overlap','few','target','start_range','start_near','nonfinite'])
def test_invalid_proposal_rejected(monkeypatch,fault):
    raw,args,results=fixture(monkeypatch)
    if fault=='model_hash':raw+=b' '
    if fault=='duplicate':args['exports'][1]=args['exports'][0].copy()
    if fault=='partial':results['0']['reconstruction_consistent']=False
    if fault=='context':results['0']['configuration_references']['workcell_sha256']='other'
    if fault=='prediction':results['0']['endpoint_diagnostics'][0]['signed_error_rad']=math.radians(3)
    if fault=='overlap':
        model=json.loads(raw);model['provenance'][0]['report_sha256']='0'*64;raw=json.dumps(model).encode();args['expected_model_sha256']=hashlib.sha256(raw).hexdigest()
    if fault=='few':args['exports']=args['exports'][:-1]
    if fault=='target':args['nominal_target_deg']=4
    if fault=='start_range':args['start_joints_rad'][3]=math.radians(9)
    if fault=='start_near':args['start_joints_rad'][3]=math.radians(2.1)
    if fault=='nonfinite':args['start_joints_rad'][3]=float('nan')
    with pytest.raises(ValueError):module.propose_model_correction(raw,**args)


@pytest.mark.parametrize('fault',['short','gap','drift','transport','corrupt','no_response','departure'])
def test_bad_synthetic_outcomes_never_pass(monkeypatch,fault):
    raw,args,_=fixture(monkeypatch);p=module.propose_model_correction(raw,**args)
    rows=trace(p,2,other=fault=='drift')
    if fault=='short':rows=rows[:20]
    if fault=='gap':rows=rows[:50]+rows[70:]
    if fault=='no_response':rows=trace(p,math.degrees(args['start_joints_rad'][3]))
    if fault=='departure':rows[-1][2][3]=math.radians(3)
    r=module.score_synthetic_correction(p,rows,transport_clean=fault!='transport',capture_issues=['CORRUPT'] if fault=='corrupt' else [])
    assert not r['simulation_passed']
