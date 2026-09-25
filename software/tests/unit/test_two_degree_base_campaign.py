"""Versioned magnitude experiment; incapable native fixtures only."""
import math
import pytest
from rocell.application.first_motion_contract import canonical
from rocell.safety.positional_campaign_authority import (
    TWO_DEGREE_BASE_SCHEMA,fixed_campaign_limits,PositionalCampaignIntent,require_correction_start,
)
from test_campaign_stream_sync import sync_body
from test_model_corrected_native_campaign import install
from test_positional_campaign_native_capture import exercise
from test_positional_campaign_native_export import bundle
from rocell.application.positional_campaign_native_export import verify_native_retained_export


def two_body(direction=1):
    body=sync_body()
    body.update(schema=TWO_DEGREE_BASE_SCHEMA,limits=fixed_campaign_limits(TWO_DEGREE_BASE_SCHEMA))
    leg=body['legs'][0]
    leg['target_rad']=leg['command']['rad']=leg['expected_start_rad']+math.radians(2*direction)
    return body


@pytest.mark.parametrize('direction',[-1,1])
@pytest.mark.parametrize('fault',[None,'read_error','write_error','cancel_before_open'])
def test_finite_two_degree_native_shape(tmp_path,monkeypatch,direction,fault):
    install(monkeypatch)
    monkeypatch.setattr('test_positional_current_context.body',lambda:two_body(direction))
    kernel,_,_,_,result=exercise(tmp_path,monkeypatch,initial_prefix=b'}\r\n',failure=fault)
    assert len(kernel.writes)==(0 if fault in ('read_error','cancel_before_open') else 1)
    assert (result['status']=='REPORTED_CAMPAIGN_COMPLETE') is (fault is None)
    assert result['cleanup']['all_handles_closed']


@pytest.mark.parametrize('direction',[-1,1])
@pytest.mark.parametrize('miss',[None,1])
def test_two_degree_export_and_miss_reconstruction(tmp_path,monkeypatch,direction,miss):
    install(monkeypatch)
    monkeypatch.setattr('test_positional_current_context.body',lambda:two_body(direction))
    path,name,_=bundle(tmp_path,monkeypatch,initial_prefix=b'}\r\n',missed_leg=miss)
    v=verify_native_retained_export(path,name)
    assert v['valid'] and v['reconstruction_consistent']
    assert v['endpoint_completion_consistent'] is (miss is None)
    assert len(v['endpoint_diagnostics'])==1
    assert v['endpoint_diagnostics'][0]['baseline_synchronization']['startup_range']==[0,3]


@pytest.mark.parametrize('fault',['axis','command','delta','limit','extra','envelope','legacy'])
def test_two_degree_contract_cannot_widen_or_change_legacy(fault):
    b=two_body();l=b['legs'][0]
    if fault=='axis':l['command']['joint']=4
    if fault=='command':l['command']['rad']+=.01
    if fault=='delta':l['command']['rad']=l['target_rad']=l['expected_start_rad']+math.radians(3)
    if fault=='limit':b['limits']['maximum_delta_deg']=3
    if fault=='extra':b['legs']*=2
    if fault=='envelope':
        b['start_joints_rad'][0]=l['expected_start_rad']=math.radians(4)
        l['command']['rad']=l['target_rad']=math.radians(6)
    if fault=='legacy':
        b['schema']='rocell.attended_positional_intent.v7';b['limits']=fixed_campaign_limits(b['schema'])
    with pytest.raises(ValueError):PositionalCampaignIntent(canonical(b))


@pytest.mark.parametrize('delta',[1.49,2.51,-2])
def test_fresh_delta_cannot_exceed_magnitude_profile(delta):
    b=two_body();start=list(b['start_joints_rad']);start[0]=b['legs'][0]['target_rad']-math.radians(delta)
    with pytest.raises(ValueError):require_correction_start(b,start)
