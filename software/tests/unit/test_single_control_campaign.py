"""Single positioning/control commands on an incapable kernel; no hardware."""
import math
import pytest
from rocell.application.first_motion_contract import canonical
from rocell.safety.positional_campaign_authority import SINGLE_SCHEMA, fixed_campaign_limits, PositionalCampaignIntent
from test_model_corrected_native_campaign import corrected_body, install
from test_positional_campaign_native_capture import exercise
from test_positional_campaign_native_export import bundle
from rocell.application.positional_campaign_native_export import verify_native_retained_export


def control_body(target=4):
    b=corrected_body();b.pop('correction')
    b.update(schema=SINGLE_SCHEMA,mode='ATTENDED_ONE_CONTROL',limits=fixed_campaign_limits(SINGLE_SCHEMA))
    start=2.021484368 if target==4 else 3.779296882
    b['start_joints_rad'][3]=math.radians(start)
    b['legs'][0].update(expected_start_rad=math.radians(start),target_rad=math.radians(target))
    b['legs'][0]['command']['rad']=math.radians(target)
    return b


@pytest.mark.parametrize('target',[2,4])
@pytest.mark.parametrize('fault',[None,'cancel_before_open','write_error'])
def test_single_control_never_has_a_second_leg(tmp_path,monkeypatch,target,fault):
    install(monkeypatch)
    monkeypatch.setattr('test_positional_current_context.body',lambda:control_body(target))
    kernel,_,_,_,result=exercise(tmp_path,monkeypatch,failure=fault)
    assert len(kernel.writes)==(0 if fault=='cancel_before_open' else 1)
    assert result['cleanup']['all_handles_closed']
    assert (result['status']=='REPORTED_CAMPAIGN_COMPLETE') is (fault is None)


@pytest.mark.parametrize('target',[2,4])
def test_control_export_reconstructs_one_target(tmp_path,monkeypatch,target):
    install(monkeypatch)
    monkeypatch.setattr('test_positional_current_context.body',lambda:control_body(target))
    path,name,_=bundle(tmp_path,monkeypatch)
    r=verify_native_retained_export(path,name)
    assert r['valid'] and r['endpoint_completion_consistent']
    assert len(r['endpoint_diagnostics'])==1
    e=r['endpoint_diagnostics'][0]
    assert e['target_rad']==e['command']['rad']==math.radians(target)


@pytest.mark.parametrize('fault',['second','unsupported','offset','limit','mode'])
def test_control_cannot_become_a_corrected_or_extra_command(fault):
    b=control_body()
    if fault=='second':b['legs']*=2
    if fault=='unsupported':
        b['legs'][0]['target_rad']=b['legs'][0]['command']['rad']=math.radians(3)
    if fault=='offset':b['legs'][0]['command']['rad']+=.001
    if fault=='limit':b['limits']['maximum_writes']=2
    if fault=='mode':b['mode']='ATTENDED_TWO_LEG'
    with pytest.raises(ValueError):PositionalCampaignIntent(canonical(b))
