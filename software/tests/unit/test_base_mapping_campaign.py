"""Bounded base command and retained reconstruction on an incapable kernel."""
import math
import pytest
from rocell.application.first_motion_contract import canonical
from rocell.safety.positional_campaign_authority import (
    BASE_SCHEMA, fixed_campaign_limits, PositionalCampaignIntent, require_correction_start,
)
from test_single_control_campaign import control_body
from test_model_corrected_native_campaign import install
from test_positional_campaign_native_capture import exercise
from test_positional_campaign_native_export import bundle
from rocell.application.positional_campaign_native_export import verify_native_retained_export


def base_body(direction=1):
    body=control_body()
    body.update(schema=BASE_SCHEMA,mode='ATTENDED_ONE_BASE_PROBE',selected_joint='b',
        limits=fixed_campaign_limits(BASE_SCHEMA))
    body['start_joints_rad'][0]=math.radians(.4)
    leg=body['legs'][0]
    leg.update(expected_start_rad=body['start_joints_rad'][0],
        target_rad=body['start_joints_rad'][0]+math.radians(direction))
    leg['command'].update(joint=1,rad=leg['target_rad'])
    return body


@pytest.mark.parametrize('direction',[-1,1])
@pytest.mark.parametrize('fault',[None,'cancel_before_open','write_error'])
def test_base_native_loop_only_one_logical_base_command(tmp_path,monkeypatch,direction,fault):
    install(monkeypatch)
    monkeypatch.setattr('test_positional_current_context.body',lambda:base_body(direction))
    kernel,_,_,_,result=exercise(tmp_path,monkeypatch,failure=fault)
    assert len(kernel.writes)==(0 if fault=='cancel_before_open' else 1)
    assert result['cleanup']['all_handles_closed']
    assert (result['status']=='REPORTED_CAMPAIGN_COMPLETE') is (fault is None)


@pytest.mark.parametrize('direction',[-1,1])
def test_portable_base_reconstruction_uses_base_not_wrist(tmp_path,monkeypatch,direction):
    install(monkeypatch)
    monkeypatch.setattr('test_positional_current_context.body',lambda:base_body(direction))
    path,name,_=bundle(tmp_path,monkeypatch)
    result=verify_native_retained_export(path,name)
    assert result['valid'] and result['endpoint_completion_consistent'],result
    row=result['endpoint_diagnostics'][0]
    assert row['selected_joint']=='b' and row['command']['joint']==1
    assert row['final_rad']==row['target_rad']


@pytest.mark.parametrize('fault',['axis','wire_axis','offset','extra','delta','limit'])
def test_base_contract_rejects_widening(fault):
    body=base_body();leg=body['legs'][0]
    if fault=='axis':body['selected_joint']='s'
    if fault=='wire_axis':leg['command']['joint']=4
    if fault=='offset':leg['command']['rad']+=.001
    if fault=='extra':body['legs']*=2
    if fault=='delta':leg['target_rad']=leg['command']['rad']=math.radians(2)
    if fault=='limit':body['limits']['maximum_writes']=2
    with pytest.raises(ValueError):PositionalCampaignIntent(canonical(body))


def test_base_fresh_start_must_preserve_direction_and_local_range():
    body=base_body()
    for base in (1.4,5.1,-1):
        start=list(body['start_joints_rad']);start[0]=math.radians(base)
        with pytest.raises(ValueError):require_correction_start(body,start)


def test_base_target_miss_holds_without_return(tmp_path,monkeypatch):
    install(monkeypatch)
    monkeypatch.setattr('test_positional_current_context.body',base_body)
    kernel,_,_,_,result=exercise(tmp_path,monkeypatch,missed_leg=1)
    assert result['status']=='HELD' and len(kernel.writes)==1


@pytest.mark.parametrize('axis',[1,2,3,4,5])
def test_base_monitor_checks_every_other_axis(axis):
    from rocell.safety.positional_campaign_authority import verify_campaign_endpoint
    body=base_body();start=body['start_joints_rad'];leg=body['legs'][0]
    final=list(start);final[0]=leg['target_rad'];final[axis]+=math.radians(1)
    rows=[(1+i*20_000_000,1+(i+1)*20_000_000,final) for i in range(250)]
    result=verify_campaign_endpoint(body,leg,rows,start=start,capture_issues=(),transport_clean=True)
    assert not result['endpoint_verified'] and result['status']=='OTHER_JOINT_CHANGED'


def test_observed_closing_brace_prefix_holds_before_base_write(tmp_path,monkeypatch):
    """Reproduce the live capture boundary without treating it as valid JSON."""
    install(monkeypatch)
    monkeypatch.setattr('test_positional_current_context.body',base_body)
    kernel,_,_,_,result=exercise(tmp_path,monkeypatch,initial_prefix=b'}\r\n')
    assert result['status']=='HELD' and result['native_submission_attempts']==0
    assert not kernel.writes and result['lifecycle']['confirmed_write_bytes']==0
    assert result['errors']==[dict(code='ValueError',stage='baseline')]
    assert result['cleanup']['all_handles_closed']
