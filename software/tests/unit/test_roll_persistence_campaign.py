"""Long single-connection capture through incapable native-shaped fixtures."""
import hashlib
import pytest
from test_roll_mapping_campaign import roll_body
from test_model_corrected_native_campaign import install
from test_positional_campaign_native_capture import exercise
from test_positional_campaign_native_export import bundle
from rocell.application.first_motion_contract import canonical
from rocell.application.positional_campaign_native_export import verify_native_retained_export
from rocell.safety.positional_campaign_authority import (
    ROLL_PERSISTENCE_SCHEMA, fixed_campaign_limits, roll_persistence_configuration,
    PositionalCampaignIntent)


def persistence_body(direction=1, version=19):
    b=roll_body(direction)
    p=roll_persistence_configuration('INCREASING' if direction==1 else 'DECREASING')
    schema=f'rocell.attended_positional_intent.v{version}'
    b.update(schema=schema, roll_probe=p, limits=fixed_campaign_limits(schema))
    b['deadline_ns']=b['issued_ns']+b['limits']['maximum_duration_s']*1_000_000_000
    b['references']['configuration_sha256']=hashlib.sha256(canonical(p)).hexdigest()
    PositionalCampaignIntent(canonical(b))
    return b


@pytest.mark.parametrize('direction', [-1,1])
def test_extended_original_export(tmp_path,monkeypatch,direction):
    install(monkeypatch)
    monkeypatch.setattr('test_positional_current_context.body',lambda:persistence_body(direction))
    root,name,_=bundle(tmp_path,monkeypatch,initial_prefix=b'}\n')
    v=verify_native_retained_export(root,name)
    assert v['valid'] and v['reconstruction_consistent'] and v['endpoint_completion_consistent'],v
    assert v['endpoint_diagnostics'][0]['persistence']['horizons'][-1]['seconds']==35


@pytest.mark.parametrize('fault', [None,'malformed','late','other_joint','short_write','write_error','cancel','miss'])
def test_extended_capture_one_write_and_cleanup(tmp_path,monkeypatch,fault):
    install(monkeypatch)
    monkeypatch.setattr('test_positional_current_context.body',persistence_body)
    kernel, captures, verdicts, _, result=exercise(tmp_path,monkeypatch,
        failure=None if fault in ('cancel','miss') else fault,
        cancel_after_write=fault=='cancel',missed_leg=1 if fault=='miss' else None)
    assert len(kernel.writes)==1
    assert result['cleanup']['all_handles_closed']
    if fault is None:
        assert result['status']=='REPORTED_CAMPAIGN_COMPLETE',result
        assert captures[-1]['finished_ns']-captures[-1]['started_ns']>34_900_000_000
        assert verdicts[0]['endpoint']['persistence']['status']=='REPORTED_ENDPOINT_PERSISTENT'
    else:
        assert result['status']!='REPORTED_CAMPAIGN_COMPLETE'


def test_delayed_change_is_retained_as_hold_not_lost_export(tmp_path,monkeypatch):
    install(monkeypatch)
    b=persistence_body()
    monkeypatch.setattr('test_positional_current_context.body',lambda:b)
    root,name,_=bundle(tmp_path,monkeypatch,
        delayed_response_target_rad=b['legs'][0]['target_rad']+.001533981)
    v=verify_native_retained_export(root,name)
    assert v['valid'] and v['reconstruction_consistent']
    assert not v['endpoint_completion_consistent']
    assert v['endpoint_diagnostics'][0]['persistence']['status']=='REPORTED_ENDPOINT_CHANGED'


def test_exhausted_read_budget_closes_without_retry(tmp_path,monkeypatch):
    install(monkeypatch)
    monkeypatch.setattr('test_positional_current_context.body',persistence_body)
    kernel,_,_,_,result=exercise(tmp_path,monkeypatch,fragment_size=5)
    assert len(kernel.writes)<=1 and result['status']!='REPORTED_CAMPAIGN_COMPLETE'


def test_persistence_reserves_observation_after_realistic_launch_overhead():
    b=persistence_body();request=PositionalCampaignIntent(canonical(b))
    # The first real attempt was held after about 3.281 s of preparation.
    # Leave preparation slack without shortening capture or cleanup reservations.
    request.require_start_time(b['issued_ns']+3_281_000_000)
    with pytest.raises(ValueError):request.require_start_time(b['issued_ns']+14_000_000_000)
    old=PositionalCampaignIntent(canonical(persistence_body(version=18)))
    with pytest.raises(ValueError):old.require_start_time(b['issued_ns']+3_281_000_000)
