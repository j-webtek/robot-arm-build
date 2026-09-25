"""Frozen-target long observations preserve earlier roll profile contracts."""
import hashlib
import pytest
from test_roll_persistence_campaign import persistence_body
from test_model_corrected_native_campaign import install
from test_positional_campaign_native_export import bundle
from test_positional_campaign_native_capture import exercise
from rocell.application.first_motion_contract import canonical
from rocell.application.positional_campaign_native_export import verify_native_retained_export
from rocell.safety.positional_campaign_authority import (
    ROLL_LONG_FIXED_SCHEMA,roll_long_fixed_configuration,fixed_campaign_limits,PositionalCampaignIntent)


def long_fixed_body(direction=1):
    b=persistence_body(direction)
    p=roll_long_fixed_configuration('INCREASING' if direction==1 else 'DECREASING')
    b.update(schema=ROLL_LONG_FIXED_SCHEMA,roll_probe=p,limits=fixed_campaign_limits(ROLL_LONG_FIXED_SCHEMA))
    b['start_joints_rad'][4]=p['expected_roll_start_rad']
    leg=b['legs'][0]
    leg.update(expected_start_rad=p['expected_roll_start_rad'],target_rad=p['target_rad'])
    leg['command']['rad']=p['target_rad']
    b['references']['configuration_sha256']=hashlib.sha256(canonical(p)).hexdigest()
    PositionalCampaignIntent(canonical(b))
    return b


@pytest.mark.parametrize('direction',[-1,1])
def test_fixed_long_originals_reconstruct(tmp_path,monkeypatch,direction):
    install(monkeypatch)
    monkeypatch.setattr('test_positional_current_context.body',lambda:long_fixed_body(direction))
    root,name,_=bundle(tmp_path,monkeypatch)
    v=verify_native_retained_export(root,name)
    assert v['valid'] and v['reconstruction_consistent'] and v['endpoint_completion_consistent']
    assert v['endpoint_diagnostics'][0]['persistence']['sample_count']>1000


@pytest.mark.parametrize('fault',['target','start','axis','speed','extra','config'])
def test_frozen_inputs_cannot_be_substituted(fault):
    b=long_fixed_body();leg=b['legs'][0]
    if fault=='target':leg['target_rad']=leg['command']['rad']=.023
    if fault=='start':b['start_joints_rad'][4]=leg['expected_start_rad']=.005
    if fault=='axis':leg['command']['joint']=4
    if fault=='speed':leg['command']['spd']=10
    if fault=='extra':b['legs']*=2
    if fault=='config':b['roll_probe']['target_rad']=.023
    b['references']['configuration_sha256']=hashlib.sha256(canonical(b['roll_probe'])).hexdigest()
    with pytest.raises(ValueError):PositionalCampaignIntent(canonical(b))


@pytest.mark.parametrize('fault',['miss','cancel','malformed','other_joint','delayed'])
def test_one_write_even_on_fault(tmp_path,monkeypatch,fault):
    install(monkeypatch);b=long_fixed_body()
    monkeypatch.setattr('test_positional_current_context.body',lambda:b)
    kernel,_,_,_,r=exercise(tmp_path,monkeypatch,
        missed_leg=1 if fault=='miss' else None,cancel_after_write=fault=='cancel',
        failure=fault if fault in ('malformed','other_joint') else None,
        delayed_response_target_rad=b['legs'][0]['target_rad']+.001533981 if fault=='delayed' else None)
    assert len(kernel.writes)==1 and r['status']!='REPORTED_CAMPAIGN_COMPLETE'
    assert r['cleanup']['all_handles_closed']
