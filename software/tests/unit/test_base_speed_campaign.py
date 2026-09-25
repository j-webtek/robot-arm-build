"""Speed-10 native-shaped execution with incapable serial, never hardware."""
import hashlib
import math
import pytest

from rocell.application.base_speed_experiment import assemble_speed_template
from rocell.application.first_motion_contract import canonical
from rocell.safety.positional_campaign_authority import PositionalCampaignIntent
from rocell.application.positional_campaign_native_export import verify_native_retained_export
from test_base_compensation_campaign import experiment_body
from test_model_corrected_native_campaign import install
from test_positional_campaign_native_export import bundle
from test_positional_campaign_native_capture import exercise


def speed_body(direction='INCREASING'):
    b=experiment_body(direction=direction)
    result=assemble_speed_template(b,b['base_experiment']).to_dict()
    result.update(issued_ns=1_000_000_000,deadline_ns=31_000_000_000)
    return result


@pytest.mark.parametrize('direction',['INCREASING','DECREASING'])
@pytest.mark.parametrize('bias',[0,.35,.6])
def test_candidate_native_export_reports_actual_error(tmp_path,monkeypatch,direction,bias):
    install(monkeypatch)
    b=speed_body(direction)
    monkeypatch.setattr('test_positional_current_context.body',lambda:b)
    path,name,_=bundle(tmp_path,monkeypatch,initial_prefix=b'}\r\n',
        response_target_rad=b['legs'][0]['target_rad']+math.radians(bias))
    result=verify_native_retained_export(path,name)
    assert result['valid'] and result['reconstruction_consistent']
    assert result['endpoint_completion_consistent'] is (bias==0)
    endpoint=result['endpoint_diagnostics'][0]
    assert endpoint['command']['spd']==10
    assert endpoint['correction']['experiment_kind']=='SPEED_CANDIDATE'
    assert not endpoint['correction']['speed_specific_model_validated']
    assert abs(endpoint['signed_error_rad'])==pytest.approx(math.radians(bias))


@pytest.mark.parametrize('fault',['speed','acc','nominal','command','model','extra_leg','spec','start'])
def test_altered_profile_rejected(fault):
    b=speed_body()
    if fault=='speed':b['legs'][0]['command']['spd']=20
    if fault=='acc':b['legs'][0]['command']['acc']=0
    if fault=='nominal':b['legs'][0]['target_rad']+=.001
    if fault=='command':b['legs'][0]['command']['rad']+=.001
    if fault=='model':b['base_speed']['proposal']['model_sha256']='f'*64
    if fault=='extra_leg':b['legs'].append(b['legs'][0])
    if fault=='spec':b['base_speed']['specification']['candidate_speed_validated']=True
    if fault=='start':b['start_joints_rad'][0]=.006135923
    b['references']['configuration_sha256']=hashlib.sha256(canonical(b['base_speed'])).hexdigest()
    with pytest.raises(ValueError):PositionalCampaignIntent(canonical(b))


@pytest.mark.parametrize('direction',['INCREASING','DECREASING'])
@pytest.mark.parametrize('fault',['malformed','late','other_joint','short_write','write_error','cancel','opposite','excursion'])
def test_faults_never_send_a_second_command(tmp_path,monkeypatch,direction,fault):
    install(monkeypatch)
    b=speed_body(direction)
    monkeypatch.setattr('test_positional_current_context.body',lambda:b)
    target=b['legs'][0]['target_rad']
    if fault=='opposite':target=b['start_joints_rad'][0]+(-.02 if direction=='INCREASING' else .02)
    if fault=='excursion':target=.2
    kernel,_,_,_,result=exercise(tmp_path,monkeypatch,
        failure=fault if fault not in ('cancel','opposite','excursion') else None,
        cancel_after_write=fault=='cancel',response_target_rad=target)
    assert len(kernel.writes)==1
    assert result['status']!='REPORTED_CAMPAIGN_COMPLETE'
    assert result['cleanup']['all_handles_closed']
    assert result['cleanup']['pending_io_count']==0
