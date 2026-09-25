"""Decreasing native profile tests; incapable serial kernel only."""
import math
import pytest
from rocell.application.first_motion_contract import canonical
from rocell.safety.positional_campaign_authority import PositionalCampaignIntent, require_correction_start
from rocell.application.positional_campaign_native_export import verify_native_retained_export
from test_base_compensation_campaign import experiment_body
from test_model_corrected_native_campaign import install
from test_positional_campaign_native_capture import exercise
from test_positional_campaign_native_export import bundle


@pytest.mark.parametrize('kind',['CORRECTED','UNCORRECTED_CONTROL'])
@pytest.mark.parametrize('response',[.4,.439453128,1.054687474,-.684826381])
def test_native_decreasing_target_and_original_export(tmp_path,monkeypatch,kind,response):
    install(monkeypatch)
    monkeypatch.setattr('test_positional_current_context.body',lambda:experiment_body(kind,'DECREASING'))
    root,name,_=bundle(tmp_path,monkeypatch,response_target_rad=math.radians(response),initial_prefix=b'}\n')
    v=verify_native_retained_export(root,name)
    assert v['valid'] and v['reconstruction_consistent']
    passed=response in (.4,.439453128)
    assert v['endpoint_completion_consistent'] is passed
    e=v['endpoint_diagnostics'][0]
    assert e['direction']=='DECREASING' and e['target_rad']==math.radians(.4)
    assert e['correction']['experiment_screen_passed'] is passed


@pytest.mark.parametrize('kind',['CORRECTED','UNCORRECTED_CONTROL'])
@pytest.mark.parametrize('fault',['direction','command','schema','model','extra','speed'])
def test_cross_branch_or_changed_commands_rejected(kind,fault):
    b=experiment_body(kind,'DECREASING')
    if fault=='direction':b['base_experiment']['direction']='INCREASING'
    if fault=='command':b['legs'][0]['command']['rad']=.04
    if fault=='schema':b['schema']='rocell.attended_positional_intent.v10'
    if fault=='model':b['base_experiment']['model_sha256']='e'*64
    if fault=='extra':b['legs']*=2
    if fault=='speed':b['legs'][0]['command']['spd']=30
    with pytest.raises(ValueError):PositionalCampaignIntent(canonical(b))


@pytest.mark.parametrize('start',[.8,.9,1.055,2,-1])
def test_actual_start_requires_both_domain_and_nominal_distance(start):
    b=experiment_body('CORRECTED','DECREASING');s=list(b['start_joints_rad']);s[0]=math.radians(start)
    with pytest.raises(ValueError):require_correction_start(b,s)


@pytest.mark.parametrize('fault,writes',[('read_error',0),('write_error',1),('cancel_before_open',0)])
def test_transport_faults_do_not_repeat(tmp_path,monkeypatch,fault,writes):
    install(monkeypatch)
    monkeypatch.setattr('test_positional_current_context.body',lambda:experiment_body('CORRECTED','DECREASING'))
    kernel,_,_,_,r=exercise(tmp_path,monkeypatch,failure=fault)
    assert len(kernel.writes)==writes and r['cleanup']['all_handles_closed']


def test_cancellation_after_submission_does_not_return(tmp_path,monkeypatch):
    install(monkeypatch)
    monkeypatch.setattr('test_positional_current_context.body',lambda:experiment_body('CORRECTED','DECREASING'))
    kernel,_,_,_,r=exercise(tmp_path,monkeypatch,cancel_after_write=True)
    assert len(kernel.writes)==1 and r['status']=='CANCELLED'


@pytest.mark.parametrize('axis',[1,2,3,4,5])
def test_decreasing_endpoint_retains_other_joint_checks(axis):
    from rocell.safety.positional_campaign_authority import verify_campaign_endpoint
    b=experiment_body('CORRECTED','DECREASING');s=b['start_joints_rad'];leg=b['legs'][0]
    final=list(s);final[0]=leg['target_rad'];final[axis]+=math.radians(1)
    rows=[(1+i*20_000_000,1+(i+1)*20_000_000,final) for i in range(250)]
    r=verify_campaign_endpoint(b,leg,rows,start=s,capture_issues=(),transport_clean=True)
    assert r['status']=='OTHER_JOINT_CHANGED' and not r['correction']['experiment_screen_passed']
