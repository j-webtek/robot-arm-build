import math
import pytest
from rocell.application.first_motion_contract import canonical
from rocell.safety.positional_campaign_authority import MIDPOINT_BASE_SCHEMA,BASE_MIDPOINT_TARGETS,fixed_campaign_limits,PositionalCampaignIntent,require_correction_start
from test_campaign_stream_sync import sync_body
from test_model_corrected_native_campaign import install
from test_positional_campaign_native_capture import exercise
from test_positional_campaign_native_export import bundle
from rocell.application.positional_campaign_native_export import verify_native_retained_export


def midpoint_body(name='negative-midpoint'):
    b=sync_body();b.update(schema=MIDPOINT_BASE_SCHEMA,limits=fixed_campaign_limits(MIDPOINT_BASE_SCHEMA))
    b['start_joints_rad'][0]=math.radians(1.054687474 if name=='negative-midpoint' else .351562491)
    l=b['legs'][0];l['expected_start_rad']=b['start_joints_rad'][0]
    l['command']['rad']=l['target_rad']=BASE_MIDPOINT_TARGETS[name]
    return b


@pytest.mark.parametrize('name',list(BASE_MIDPOINT_TARGETS))
@pytest.mark.parametrize('fault',[None,'read_error','write_error','cancel_before_open'])
def test_midpoint_native_shape(tmp_path,monkeypatch,name,fault):
    install(monkeypatch);monkeypatch.setattr('test_positional_current_context.body',lambda:midpoint_body(name))
    kernel,_,_,_,r=exercise(tmp_path,monkeypatch,initial_prefix=b'}\r\n',failure=fault)
    assert len(kernel.writes)==(0 if fault in ('read_error','cancel_before_open') else 1)
    assert (r['status']=='REPORTED_CAMPAIGN_COMPLETE') is (fault is None)
    assert r['cleanup']['all_handles_closed']


@pytest.mark.parametrize('name',list(BASE_MIDPOINT_TARGETS))
@pytest.mark.parametrize('miss',[None,1])
def test_midpoint_portable_export(tmp_path,monkeypatch,name,miss):
    install(monkeypatch);monkeypatch.setattr('test_positional_current_context.body',lambda:midpoint_body(name))
    path,file,_=bundle(tmp_path,monkeypatch,initial_prefix=b'}\r\n',missed_leg=miss)
    r=verify_native_retained_export(path,file)
    assert r['valid'] and r['reconstruction_consistent']
    assert r['endpoint_completion_consistent'] is (miss is None)
    assert r['endpoint_diagnostics'][0]['command']['rad']==BASE_MIDPOINT_TARGETS[name]


@pytest.mark.parametrize('fault',['angle','joint','extra','limit','nominal','start'])
def test_midpoint_is_not_an_arbitrary_target_path(fault):
    b=midpoint_body();l=b['legs'][0]
    if fault=='angle':l['target_rad']=l['command']['rad']=math.radians(-.7)
    if fault=='joint':l['command']['joint']=2
    if fault=='extra':b['legs']*=2
    if fault=='limit':b['limits']['maximum_delta_deg']=3
    if fault=='nominal':l['target_rad']+=.01
    if fault=='start':b['start_joints_rad'][0]=l['expected_start_rad']=math.radians(4)
    with pytest.raises(ValueError):PositionalCampaignIntent(canonical(b))


@pytest.mark.parametrize('delta',[.49,2.51,-1])
def test_midpoint_actual_start_bounds(delta):
    b=midpoint_body('positive-midpoint');s=list(b['start_joints_rad']);s[0]=b['legs'][0]['target_rad']-math.radians(delta)
    with pytest.raises(ValueError):require_correction_start(b,s)
