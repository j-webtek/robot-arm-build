"""Fixed roll targets preserve the meaning of the older relative profile."""
import hashlib
import pytest
from rocell.application.first_motion_contract import canonical
from rocell.safety.positional_campaign_authority import (
    ROLL_FIXED_SCHEMA,PositionalCampaignIntent,fixed_campaign_limits,
    roll_fixed_configuration,require_correction_start,
)
from test_roll_mapping_campaign import roll_body
from test_model_corrected_native_campaign import install
from test_positional_campaign_native_capture import exercise
from test_positional_campaign_native_export import bundle
from rocell.application.positional_campaign_native_export import verify_native_retained_export


def fixed_roll_body(direction=1):
    b=roll_body(direction)
    p=roll_fixed_configuration('INCREASING' if direction==1 else 'DECREASING')
    b.update(schema=ROLL_FIXED_SCHEMA,roll_probe=p,limits=fixed_campaign_limits(ROLL_FIXED_SCHEMA))
    b['start_joints_rad'][4]=p['expected_roll_start_rad']
    leg=b['legs'][0];leg.update(expected_start_rad=p['expected_roll_start_rad'],target_rad=p['target_rad'])
    leg['command']['rad']=p['target_rad']
    b['references']['configuration_sha256']=hashlib.sha256(canonical(p)).hexdigest()
    return b


@pytest.mark.parametrize('direction',[-1,1])
def test_fixed_export_reconstructs_command_and_report(tmp_path,monkeypatch,direction):
    install(monkeypatch)
    b=fixed_roll_body(direction)
    monkeypatch.setattr('test_positional_current_context.body',lambda:b)
    root,name,_=bundle(tmp_path,monkeypatch,initial_prefix=b'}\n')
    v=verify_native_retained_export(root,name)
    assert v['valid'] and v['reconstruction_consistent'] and v['endpoint_completion_consistent']
    assert v['endpoint_diagnostics'][0]['command']==b['legs'][0]['command']


@pytest.mark.parametrize('direction',[-1,1])
@pytest.mark.parametrize('fault',['miss','malformed','late','short_write','write_error','other_joint','cancel'])
def test_fixed_roll_fault_closes_without_retry(tmp_path,monkeypatch,direction,fault):
    install(monkeypatch)
    monkeypatch.setattr('test_positional_current_context.body',lambda:fixed_roll_body(direction))
    kernel,_,_,_,r=exercise(tmp_path,monkeypatch,failure=None if fault in ('miss','cancel') else fault,
        missed_leg=1 if fault=='miss' else None,cancel_after_write=fault=='cancel')
    assert len(kernel.writes)==1 and r['status']!='REPORTED_CAMPAIGN_COMPLETE'
    assert r['cleanup']['all_handles_closed']


@pytest.mark.parametrize('fault',['target','anchor','axis','speed','extra','config'])
def test_fixed_contract_rejects_substitution(fault):
    b=fixed_roll_body();leg=b['legs'][0]
    if fault=='target':leg['target_rad']=leg['command']['rad']=.02
    if fault=='anchor':b['start_joints_rad'][4]=leg['expected_start_rad']=-.001533981
    if fault=='axis':leg['command']['joint']=4
    if fault=='speed':leg['command']['spd']=10
    if fault=='extra':b['legs']*=2
    if fault=='config':b['roll_probe']['target_rad']=.02
    b['references']['configuration_sha256']=hashlib.sha256(canonical(b['roll_probe'])).hexdigest()
    with pytest.raises(ValueError):PositionalCampaignIntent(canonical(b))


def test_reported_arrival_is_not_the_next_anchor():
    b=fixed_roll_body(-1);wrong=list(b['start_joints_rad']);wrong[4]=.015919311519943295
    with pytest.raises(ValueError):require_correction_start(b,wrong)
