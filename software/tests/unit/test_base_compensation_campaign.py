"""Fixed base inverse/control contract; all native I/O uses incapable fixtures."""
import hashlib
import math
from copy import deepcopy

import pytest

from rocell.application.first_motion_contract import canonical
from rocell.application.base_correction_proposal import BaseCorrectionProposal
from rocell.safety.positional_campaign_authority import (
    BASE_CORRECTION_SCHEMA, BASE_CONTROL_SCHEMA, PositionalCampaignIntent,
    fixed_campaign_limits, require_correction_start,
)
from test_campaign_stream_sync import sync_body
from test_model_corrected_native_campaign import install
from test_positional_campaign_native_capture import exercise
from test_positional_campaign_native_export import bundle
from rocell.application.positional_campaign_native_export import verify_native_retained_export


def proposal(start, references, direction='INCREASING'):
    """Synthetic provenance for contract tests, never evidence for live staging."""
    p=dict(schema='rocell.offline_base_correction_proposal.v1',
        nominal_target_rad=math.radians(1),proposed_command_target_rad=0.04076651868282478,
        predicted_final_rad=math.radians(1),direction='INCREASING',
        expected_start_joints_rad=list(start),start_is_historical_only=True,
        start_domain_rad=[0.006135923,0.007669904],
        command_domain_rad=[0.025123196519943297,0.04257648903988659],
        model_file_sha256='fa8158f348758829ec29452525ccd97b77c34da97778b4073a031a3677884cb5',
        model_sha256='643f9b946319c400de08f2a508700ee27afd500f55e084dc8c7a5cf7f5d40852',
        training_dataset_sha256='aba418750431a590fc96d2c303bf3966d8b8b25445b51bdbc282fde97eb37b5c',
        held_out_checks=[],context_references={k:references[k] for k in (
            'native_controller_review_sha256','protocol_review_sha256','workcell_sha256','tool_payload_sha256')},
        maximum_commands=1,spd=20,acc=1,maximum_delta_deg=2.5,observation_s=5,
        arrival_tolerance_deg=.5,experiment_error_screen_deg=.25,automatic_retry=False,
        motion_authorized=False,compensation_enabled=False,physical_accuracy_verified=False,
        fresh_baseline_required=True,native_integration_status='NOT_IMPLEMENTED_FOR_THIS_SCHEMA')
    if direction=='DECREASING':
        p.update(schema='rocell.offline_base_correction_proposal.v2',direction=direction,
            nominal_target_rad=math.radians(.4),predicted_final_rad=math.radians(.4),
            proposed_command_target_rad=-0.011952475158143525,
            start_domain_rad=[.009203885,.018407769],
            command_domain_rad=[-.01649881603988659,-.008249407519943295])
    return p


def experiment_body(kind='CORRECTED',direction='INCREASING'):
    b=sync_body()
    schema=BASE_CORRECTION_SCHEMA if kind=='CORRECTED' else BASE_CONTROL_SCHEMA
    if direction=='DECREASING':
        from rocell.safety.positional_campaign_authority import DECREASING_BASE_CORRECTION_SCHEMA, DECREASING_BASE_CONTROL_SCHEMA
        schema=DECREASING_BASE_CORRECTION_SCHEMA if kind=='CORRECTED' else DECREASING_BASE_CONTROL_SCHEMA
    b.update(schema=schema,limits=fixed_campaign_limits(schema))
    b['start_joints_rad'][0]=.018407769 if direction=='DECREASING' else .007669904
    p=proposal(b['start_joints_rad'],b['references'],direction)
    b['base_experiment']=p
    b['references']['configuration_sha256']=hashlib.sha256(canonical(p)).hexdigest()
    b['legs']=[dict(leg_id='leg-01',expected_start_rad=b['start_joints_rad'][0],
        target_rad=p['nominal_target_rad'],command=dict(T=101,joint=1,
            rad=p['proposed_command_target_rad'] if kind=='CORRECTED' else p['nominal_target_rad'],spd=20,acc=1))]
    return b


def staging_inputs(monkeypatch, configuration, kind, direction='INCREASING'):
    """Replace only original-evidence rebuilding; native staging remains real."""
    args=deepcopy(configuration)
    args.pop('targets_rad')
    args['start_joints_rad'][0]=.018407769 if direction=='DECREASING' else .007669904
    refs={k:hashlib.sha256(raw).hexdigest() for k,raw in args['originals'].items()}
    p=proposal(args['start_joints_rad'],refs,direction)
    def incapable_proposer(*a,**kw):
        assert kw['start_joints_rad']==args['start_joints_rad']
        return BaseCorrectionProposal(canonical(p))
    name='propose_decreasing_base_correction' if direction=='DECREASING' else 'propose_base_correction'
    monkeypatch.setattr('rocell.application.base_correction_proposal.'+name,incapable_proposer)
    args.update(model_raw=b'fixture-only',expected_model_sha256='f'*64,
        training_exports=[],held_out=[],experiment_kind=kind,direction=direction)
    return args


@pytest.mark.parametrize('kind',['CORRECTED','UNCORRECTED_CONTROL'])
@pytest.mark.parametrize('response',[1,1.35,2.3357494659670794])
def test_native_and_export_score_desired_not_motor(tmp_path,monkeypatch,kind,response):
    install(monkeypatch)
    monkeypatch.setattr('test_positional_current_context.body',lambda:experiment_body(kind))
    path,name,_=bundle(tmp_path,monkeypatch,initial_prefix=b'}\r\n',response_target_rad=math.radians(response))
    r=verify_native_retained_export(path,name)
    assert r['valid'] and r['reconstruction_consistent']
    assert r['endpoint_completion_consistent'] is (response==1)
    e=r['endpoint_diagnostics'][0]
    assert e['target_rad']==math.radians(1)
    assert e['correction']['experiment_kind']==kind
    assert e['correction']['experiment_screen_passed'] is (response==1)
    assert e['command']['rad']==experiment_body(kind)['legs'][0]['command']['rad']


@pytest.mark.parametrize('kind',['CORRECTED','UNCORRECTED_CONTROL'])
@pytest.mark.parametrize('fault',['command','nominal','joint','extra','limits','hash','model','domain','context','kind'])
def test_modified_experiment_rejected(kind,fault):
    b=experiment_body(kind)
    if fault=='command':b['legs'][0]['command']['rad']+=.001
    if fault=='nominal':b['legs'][0]['target_rad']+=.001
    if fault=='joint':b['legs'][0]['command']['joint']=4
    if fault=='extra':b['legs']*=2
    if fault=='limits':b['limits']['maximum_writes']=2
    if fault=='hash':b['references']['configuration_sha256']='d'*64
    if fault=='model':b['base_experiment']['model_sha256']='e'*64
    if fault=='domain':b['base_experiment']['start_domain_rad']=[0,1]
    if fault=='context':b['references']['workcell_sha256']='d'*64
    if fault=='kind':b['schema']=BASE_CONTROL_SCHEMA if kind=='CORRECTED' else BASE_CORRECTION_SCHEMA
    if fault in ('model','domain'):
        b['references']['configuration_sha256']=hashlib.sha256(canonical(b['base_experiment'])).hexdigest()
    with pytest.raises(ValueError):PositionalCampaignIntent(canonical(b))


@pytest.mark.parametrize('kind',['CORRECTED','UNCORRECTED_CONTROL'])
@pytest.mark.parametrize('start',[0.006135923-1e-9,0.007669904+1e-9,0.015339808])
def test_fresh_start_cannot_use_generic_half_degree_tolerance(kind,start):
    b=experiment_body(kind);s=list(b['start_joints_rad']);s[0]=start
    with pytest.raises(ValueError):require_correction_start(b,s)


@pytest.mark.parametrize('kind',['CORRECTED','UNCORRECTED_CONTROL'])
@pytest.mark.parametrize('fault,writes',[('read_error',0),('write_error',1),('cancel_before_open',0)])
def test_fault_never_retries(tmp_path,monkeypatch,kind,fault,writes):
    install(monkeypatch)
    monkeypatch.setattr('test_positional_current_context.body',lambda:experiment_body(kind))
    kernel,_,_,_,r=exercise(tmp_path,monkeypatch,failure=fault)
    assert len(kernel.writes)==writes and r['cleanup']['all_handles_closed']


@pytest.mark.parametrize('kind',['CORRECTED','UNCORRECTED_CONTROL'])
def test_cancel_after_write_holds(tmp_path,monkeypatch,kind):
    install(monkeypatch)
    monkeypatch.setattr('test_positional_current_context.body',lambda:experiment_body(kind))
    kernel,_,verdicts,_,r=exercise(tmp_path,monkeypatch,cancel_after_write=True)
    assert len(kernel.writes)==1 and not verdicts and r['status']=='CANCELLED'


@pytest.mark.parametrize('kind',['CORRECTED','UNCORRECTED_CONTROL'])
@pytest.mark.parametrize('axis',[1,2,3,4,5])
def test_experiment_retains_all_other_joint_checks(kind,axis):
    from rocell.safety.positional_campaign_authority import verify_campaign_endpoint
    b=experiment_body(kind);start=b['start_joints_rad'];leg=b['legs'][0]
    final=list(start);final[0]=leg['target_rad'];final[axis]+=math.radians(1)
    rows=[(1+i*20_000_000,1+(i+1)*20_000_000,final) for i in range(250)]
    e=verify_campaign_endpoint(b,leg,rows,start=start,capture_issues=(),transport_clean=True)
    assert e['status']=='OTHER_JOINT_CHANGED' and not e['endpoint_verified']
    assert not e['correction']['experiment_screen_passed']


@pytest.mark.parametrize('kind',['CORRECTED','UNCORRECTED_CONTROL'])
def test_experiment_never_skips_second_corrupt_baseline_line(tmp_path,monkeypatch,kind):
    install(monkeypatch)
    monkeypatch.setattr('test_positional_current_context.body',lambda:experiment_body(kind))
    kernel,_,_,_,r=exercise(tmp_path,monkeypatch,initial_prefix=b'}\nBAD\n')
    assert r['status']=='HELD' and not kernel.writes


def test_sync_profile_rosters_remain_aligned():
    from rocell.arm.campaign_stream_sync import SYNC_SCHEMAS
    from rocell.safety.positional_campaign_authority import SYNC_BASE_SCHEMAS
    assert SYNC_SCHEMAS==SYNC_BASE_SCHEMAS
