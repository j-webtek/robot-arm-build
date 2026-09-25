"""Exercise the real native-shaped collector with an incapable kernel only."""
import hashlib
import json
import math
from copy import deepcopy
import pytest

from rocell.application.first_motion_contract import canonical
from rocell.safety.positional_campaign_authority import (
    CORRECTION_SCHEMA, BOUNDED_CHECKS, PositionalCampaignIntent, fixed_campaign_limits)
from test_positional_campaign_authority import body as old_body, review as old_review
from test_endpoint_current_context import fixture as controller_fixture
from test_positional_campaign_native_capture import exercise
from test_positional_campaign_native_export import bundle
from rocell.application.positional_campaign_native_export import verify_native_retained_export
from rocell.application.positional_campaign_native_review import review_native_campaign


def model_inputs(monkeypatch, configuration):
    """Use the real proposer with synthetic export-verifier records."""
    from test_wrist_model_correction import fixture
    raw,args,results=fixture(monkeypatch)
    context={k:hashlib.sha256(configuration['originals'][k]).hexdigest() for k in (
        'native_controller_review_sha256','protocol_review_sha256','workcell_sha256','tool_payload_sha256')}
    model=json.loads(raw)
    model['provenance'][0]['configuration_references']=context
    raw=canonical(model)
    for result in results.values():result['configuration_references']=context
    config=dict(configuration)
    config.pop('targets_rad')
    return dict(config,model_raw=raw,expected_model_sha256=hashlib.sha256(raw).hexdigest(),exports=args['exports'])


def corrected_body():
    b=old_body()
    b.update(schema=CORRECTION_SCHEMA,mode='ATTENDED_ONE_CORRECTION',
             limits=fixed_campaign_limits(CORRECTION_SCHEMA))
    b['references']['bounded_motion_risk_sha256']=b['references'].pop('stop_qualification_sha256')
    b['references']['native_controller_review_sha256']=controller_fixture()[-1].binding_sha256
    b['start_joints_rad'][3]=math.radians(3.779296882)
    command=math.radians(2-.966796894)
    p=dict(schema='rocell.offline_model_correction_proposal.v1',nominal_target_deg=2,
        proposed_command_target_deg=2-.966796894,proposed_command_target_rad=command,
        bias_deg=.966796894,uncorrected_mean_absolute_error_deg=.900390625,
        direction='DECREASING',expected_start_joints_rad=list(b['start_joints_rad']),
        motion_authorized=False,compensation_enabled=False,automatic_retry=False,
        maximum_commands=1,spd=20,acc=1,arrival_tolerance_deg=.5,observation_s=5,
        maximum_delta_deg=5,correction_screen_maximum_error_deg=.25,
        context_references={k:b['references'][k] for k in ('native_controller_review_sha256',
            'protocol_review_sha256','workcell_sha256','tool_payload_sha256')})
    b['correction']=p
    b['references']['configuration_sha256']=hashlib.sha256(canonical(p)).hexdigest()
    b['legs']=[dict(leg_id='leg-01',expected_start_rad=b['start_joints_rad'][3],
        target_rad=math.radians(2),command=dict(T=101,joint=4,rad=command,spd=20,acc=1))]
    return b


def install(monkeypatch):
    import test_positional_current_context as context
    monkeypatch.setattr(context,'body',corrected_body)
    monkeypatch.setattr(context,'review',lambda:dict(old_review(),checks=dict.fromkeys(BOUNDED_CHECKS,True)))


@pytest.mark.parametrize('field',['nominal','command','bias','config','context','second','limit','mode'])
def test_changed_correction_contract_rejected(field):
    b=corrected_body()
    if field=='nominal':b['legs'][0]['target_rad']=b['legs'][0]['command']['rad']
    if field=='command':b['legs'][0]['command']['rad']=math.radians(2)
    if field=='bias':b['correction']['bias_deg']=.2
    if field=='config':b['references']['configuration_sha256']='d'*64
    if field=='context':b['references']['workcell_sha256']='d'*64
    if field=='second':b['legs'].append(deepcopy(b['legs'][0]))
    if field=='limit':b['limits']['maximum_writes']=2
    if field=='mode':b['mode']='ATTENDED_TWO_LEG'
    with pytest.raises(ValueError):PositionalCampaignIntent(canonical(b))


@pytest.mark.parametrize('reaches_nominal',[True,False])
def test_native_shaped_dispatch_scores_nominal_and_reconstructs(tmp_path,monkeypatch,reaches_nominal):
    install(monkeypatch)
    kernel,captures,verdicts,_,result=exercise(tmp_path,monkeypatch,
        response_target_rad=math.radians(2) if reaches_nominal else None)
    assert len(kernel.writes)==1 and len(captures)==2
    assert result['status']==('REPORTED_CAMPAIGN_COMPLETE' if reaches_nominal else 'HELD'),result
    endpoint=verdicts[0]['endpoint']
    assert endpoint['endpoint_verified'] is reaches_nominal
    assert endpoint['correction']['improvement_screen_passed'] is reaches_nominal
    assert endpoint['correction']['command_endpoint_diagnostic']['endpoint_verified'] is not reaches_nominal
    body=corrected_body()
    body['references']['runtime_sha256']=hashlib.sha256(canonical(dict(fixture_only=True))).hexdigest()
    request=PositionalCampaignIntent(canonical(body))
    assert review_native_campaign(request,result)['valid']


@pytest.mark.parametrize('reaches_nominal',[True,False])
def test_portable_original_export_preserves_both_targets(tmp_path,monkeypatch,reaches_nominal):
    install(monkeypatch)
    path,name,_=bundle(tmp_path,monkeypatch,
        response_target_rad=math.radians(2) if reaches_nominal else None)
    result=verify_native_retained_export(path,name)
    assert result['valid'] and result['reconstruction_consistent']
    assert result['endpoint_completion_consistent'] is reaches_nominal
    e=result['endpoint_diagnostics'][0]
    assert e['target_rad']==math.radians(2) and e['command']['rad']!=e['target_rad']
    assert e['correction']['improvement_screen_passed'] is reaches_nominal


@pytest.mark.parametrize('failure,writes',[('cancel_before_open',0),('write_error',1),('read_error',0)])
def test_failures_never_retry(tmp_path,monkeypatch,failure,writes):
    install(monkeypatch)
    kernel,_,verdicts,_,result=exercise(tmp_path,monkeypatch,failure=failure)
    assert len(kernel.writes)==writes and not verdicts
    assert result['cleanup']['all_handles_closed']


def test_cancel_after_corrected_write_cannot_replay(tmp_path,monkeypatch):
    install(monkeypatch)
    kernel,_,verdicts,_,result=exercise(tmp_path,monkeypatch,cancel_after_write=True)
    assert len(kernel.writes)==1 and not verdicts and result['status']=='CANCELLED'
