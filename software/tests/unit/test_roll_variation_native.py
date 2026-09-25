"""v22 uses real admission/capture/export code with incapable fake serial."""
import hashlib
import pytest
from rocell.application.first_motion_contract import canonical
from rocell.arm.roll_target_variation import experiment_case
from rocell.safety.positional_campaign_authority import (
    ROLL_VARIATION_SCHEMA, PositionalCampaignIntent, roll_variation_configuration,
    fixed_campaign_limits, require_correction_start)
from rocell.application.positional_campaign_native_export import verify_native_retained_export
from test_roll_framed_campaign import framed_body
from test_model_corrected_native_campaign import install
from test_positional_campaign_native_export import bundle
from test_positional_campaign_native_capture import exercise
from test_arrival_wizard_service import make_service, _ticket

CASES=('low','nominal','high','return-low','return-nominal','return-high')


def variation_body(case_id='nominal'):
    body=framed_body()
    config=roll_variation_configuration(case_id)
    body.update(schema=ROLL_VARIATION_SCHEMA,roll_probe=config,
        limits=fixed_campaign_limits(ROLL_VARIATION_SCHEMA),
        start_joints_rad=list(config['expected_start_joints_rad']))
    leg=body['legs'][0]
    leg.update(expected_start_rad=config['expected_roll_start_rad'],target_rad=config['target_rad'])
    leg['command']['rad']=config['target_rad']
    body['references']['configuration_sha256']=hashlib.sha256(canonical(config)).hexdigest()
    PositionalCampaignIntent(canonical(body))
    return body


@pytest.mark.parametrize('case_id',CASES)
def test_case_geometry_matches_simulator(case_id):
    b=variation_body(case_id);s=experiment_case(case_id)
    assert b['start_joints_rad']==s['start_joints_rad']
    assert b['legs'][0]['command']==dict(T=101,joint=5,rad=s['target_rad'],spd=20,acc=1)
    assert b['limits']['maximum_writes']==1 and b['limits']['observation_s']==35


@pytest.mark.parametrize('case_id',CASES)
def test_native_capture_and_export_reconstruct(tmp_path,monkeypatch,case_id):
    install(monkeypatch)
    monkeypatch.setattr('test_positional_current_context.body',lambda:variation_body(case_id))
    root,name,_=bundle(tmp_path,monkeypatch,fragment_size=79)
    report=verify_native_retained_export(root,name)
    assert report['valid'] and report['reconstruction_consistent'] and report['endpoint_completion_consistent']
    row=report['endpoint_diagnostics'][0]
    assert row['roll_case_id']==case_id
    assert row['quality_assessment']['next_start_status']=='REPORTED_MATCH'
    assert row['persistence']['status']=='REPORTED_ENDPOINT_PERSISTENT'
    assert not row['cross_window_framing']['crossing_frame_counted_as_post']


@pytest.mark.parametrize('fault',['target','start','axis','speed','config','extra','old_schema'])
def test_substitutions_rejected(fault):
    b=variation_body();leg=b['legs'][0]
    if fault=='target':leg['target_rad']=leg['command']['rad']=.024
    if fault=='start':b['start_joints_rad'][1]+=.001
    if fault=='axis':leg['command']['joint']=4
    if fault=='speed':leg['command']['spd']=10
    if fault=='config':b['roll_probe']['target_rad']=.024
    if fault=='extra':b['legs']*=2
    if fault=='old_schema':b['schema']='rocell.attended_positional_intent.v21'
    b['references']['configuration_sha256']=hashlib.sha256(canonical(b['roll_probe'])).hexdigest()
    with pytest.raises(ValueError):PositionalCampaignIntent(canonical(b))


@pytest.mark.parametrize('axis',range(6))
def test_fresh_full_pose_must_match(axis):
    b=variation_body();pose=b['start_joints_rad'].copy();pose[axis]+=.001
    with pytest.raises(ValueError):require_correction_start(b,pose)


@pytest.mark.parametrize('fault',['delayed','malformed','other_joint','miss','cancel'])
def test_faults_never_queue_another_write(tmp_path,monkeypatch,fault):
    install(monkeypatch);b=variation_body()
    monkeypatch.setattr('test_positional_current_context.body',lambda:b)
    kernel,_,_,_,result=exercise(tmp_path,monkeypatch,fragment_size=79,
        delayed_response_target_rad=b['legs'][0]['target_rad']+.001533981 if fault=='delayed' else None,
        failure=fault if fault in ('malformed','other_joint') else None,
        missed_leg=1 if fault=='miss' else None,cancel_after_write=fault=='cancel')
    assert len(kernel.writes)==1 and result['status']!='REPORTED_CAMPAIGN_COMPLETE'
    assert result['cleanup']['all_handles_closed']


@pytest.mark.parametrize('case_id',CASES)
def test_wizard_stages_case_without_hardware(make_service,monkeypatch,case_id):
    from test_wizard_positional_campaign_native import inputs
    from rocell.safety.positional_campaign_authority import BOUNDED_CHECKS
    service,runner,_=make_service(mode='physical')
    monkeypatch.setattr(service,'_powered_setup_context',lambda:'fixture-powered-context')
    args=inputs();args.pop('targets_rad')
    args.update(start_joints_rad=variation_body(case_id)['start_joints_rad'],case_id=case_id)
    preview=service.configure_roll_target_variation(**args)
    assert preview['roll_case_id']==case_id
    assert preview['start_joints_rad']==args['start_joints_rad']
    assert len(preview['legs'])==1 and preview['legs'][0]['command']['joint']==5
    ticket=_ticket(service,'run_positional_campaign',dict(operator_id='operator',**dict.fromkeys(BOUNDED_CHECKS,True)))
    assert 'At most 1 wrist roll commands' in ' '.join(ticket['effects'])
    assert not runner.calls and not preview['motion_authorized']


@pytest.mark.parametrize('direction',['INCREASING','DECREASING'])
@pytest.mark.parametrize('mode',['complete','miss','cancel'])
def test_owned_coordinator_end_to_end(tmp_path,monkeypatch,direction,mode):
    from test_wizard_positional_campaign_execution import test_final_click_through_actual_collector_and_portable_export as run
    run(tmp_path,monkeypatch,mode,targets_deg=(1,),synchronize=True,base_magnitude=1,
        direction=direction,roll='variation')
