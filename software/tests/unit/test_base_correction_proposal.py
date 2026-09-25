"""Offline proposal evidence gates with explicitly synthetic original readers."""
import hashlib
import math
from copy import deepcopy
import pytest
from rocell.application.first_motion_contract import canonical
from rocell.application.base_endpoint_dataset import fit_local_base_lines,predict_unseen_base_target
from rocell.application.base_correction_proposal import propose_base_correction,score_synthetic_base_correction
from test_base_endpoint_dataset import data


def inputs(monkeypatch, *, decreasing=False):
    training=data()
    if decreasing:
        for i,row in enumerate(training['rows']):
            if row['direction']=='DECREASING':
                lower=math.degrees(row['command_rad'])<1.5
                row['command_rad']=math.radians(-1 if lower else -.5)
                row['final_joints_rad'][0]=math.radians(.35 if lower else .45)
                row['start_joints_rad'][0]=math.radians(.53 if i%2 else 1.05)
    model=fit_local_base_lines(training);raw=canonical(model);digest=hashlib.sha256(raw).hexdigest()
    observations={};held=[]
    for i,(target,start) in enumerate(((1.25,0),(1.75,0),(-.75,1.05) if decreasing else (1.5,3))):
        s=[math.radians(start),0,0,0,0,0]
        p=predict_unseen_base_target(model,target_rad=math.radians(target),start_joints_rad=s)
        p.update(model_file_sha256=digest,comparison_predeclared=True)
        encoded=canonical(p)
        r=dict(campaign_id=f'held-{i}',report_sha256=str(i+1)*64,context=model['context'],
            start_joints_rad=s,command_rad=p['target_rad'],target_rad=p['target_rad'],
            final_joints_rad=[p['predicted_final_rad'],0,0,0,0,0],direction=p['direction'])
        observations[str(i)]=dict(rows=[r]);held.append(dict(export={'fixture':str(i)},prediction_raw=encoded,prediction_sha256=hashlib.sha256(encoded).hexdigest()))
    def reader(selection):
        return deepcopy(training if selection==[{'fixture':'training'}] else observations[selection[0]['fixture']])
    monkeypatch.setattr('rocell.application.base_correction_proposal.build_base_dataset',reader)
    return dict(model_raw=raw,expected_model_sha256=digest,training_exports=[{'fixture':'training'}],held_out=held,start_joints_rad=[math.radians(1.05) if decreasing else 0,0,0,0,0,0])


def test_decreasing_proposal_uses_its_own_branch_and_cannot_use_native_positive_profile(monkeypatch):
    from rocell.application.base_correction_proposal import propose_decreasing_base_correction
    from rocell.safety.positional_campaign_authority import PositionalCampaignIntent
    from test_base_compensation_campaign import experiment_body
    args=inputs(monkeypatch,decreasing=True)
    proposal=propose_decreasing_base_correction(**args);p=proposal.to_dict()
    assert p['schema']=='rocell.offline_base_correction_proposal.v2'
    assert p['direction']=='DECREASING' and math.degrees(p['nominal_target_rad'])==pytest.approx(.4)
    assert math.degrees(p['proposed_command_target_rad'])==pytest.approx(-.75)
    assert p['native_integration_status']=='IMPLEMENTED_V12_V13_LOCAL_EXPERIMENT_ONLY'
    b=experiment_body();b['base_experiment']=p
    b['references']['configuration_sha256']=proposal.sha256
    with pytest.raises(ValueError):PositionalCampaignIntent(canonical(b))
    final=list(p['expected_start_joints_rad']);final[0]=p['nominal_target_rad']
    rows=[(1+i*20_000_000,1+(i+1)*20_000_000,final) for i in range(250)]
    assert score_synthetic_base_correction(proposal,rows)['experiment_screen_passed']


@pytest.mark.parametrize('fault',['start_domain','short_nominal_move','pose','model_hash','prediction_hash'])
def test_decreasing_proposal_rejects_invalid_start_or_evidence(monkeypatch,fault):
    from rocell.application.base_correction_proposal import propose_decreasing_base_correction
    args=inputs(monkeypatch,decreasing=True)
    if fault=='start_domain':args['start_joints_rad'][0]=math.radians(1.1)
    if fault=='short_nominal_move':args['start_joints_rad'][0]=math.radians(.8)
    if fault=='pose':args['start_joints_rad'][1]=math.radians(1)
    if fault=='model_hash':args['expected_model_sha256']='f'*64
    if fault=='prediction_hash':args['held_out'][0]['prediction_sha256']='f'*64
    with pytest.raises(ValueError):propose_decreasing_base_correction(**args)


def test_inverse_is_bounded_and_cannot_authorize_motion(monkeypatch):
    p=propose_base_correction(**inputs(monkeypatch)).to_dict()
    assert math.degrees(p['nominal_target_rad'])==pytest.approx(1)
    assert math.degrees(p['proposed_command_target_rad'])==pytest.approx(1.5)
    assert not p['motion_authorized'] and not p['compensation_enabled']
    assert p['native_integration_status']=='IMPLEMENTED_V10_V11_LOCAL_EXPERIMENT_ONLY'


@pytest.mark.parametrize('fault',['model_hash','model_rebuild','prediction_hash','prediction_value','duplicate','start','pose'])
def test_inverse_evidence_cannot_be_changed(monkeypatch,fault):
    args=inputs(monkeypatch)
    if fault=='model_hash':args['expected_model_sha256']='f'*64
    if fault=='model_rebuild':
        import json
        m=json.loads(args['model_raw']);m['models'][0]['slope']=1.5;args['model_raw']=canonical(m);args['expected_model_sha256']=hashlib.sha256(args['model_raw']).hexdigest()
    if fault=='prediction_hash':args['held_out'][0]['prediction_sha256']='f'*64
    if fault=='prediction_value':
        import json
        item=args['held_out'][0];p=json.loads(item['prediction_raw']);p['predicted_final_rad']+=.01
        item['prediction_raw']=canonical(p);item['prediction_sha256']=hashlib.sha256(item['prediction_raw']).hexdigest()
    if fault=='duplicate':args['held_out'][1]=args['held_out'][0]
    if fault=='start':args['start_joints_rad'][0]=math.radians(.2)
    if fault=='pose':args['start_joints_rad'][1]=math.radians(1)
    with pytest.raises(ValueError):propose_base_correction(**args)


@pytest.mark.parametrize('fault',[None,'motor_target','other_joint','gap','short'])
def test_synthetic_scoring_uses_desired_endpoint(monkeypatch,fault):
    proposal=propose_base_correction(**inputs(monkeypatch));p=proposal.to_dict()
    final=list(p['expected_start_joints_rad']);final[0]=p['nominal_target_rad']
    if fault=='motor_target':final[0]=p['proposed_command_target_rad']
    if fault=='other_joint':final[2]=math.radians(1)
    rows=[(1+i*20_000_000,1+(i+1)*20_000_000,final) for i in range(250)]
    if fault=='gap':rows=rows[:20]+rows[40:]
    if fault=='short':rows=rows[:25]
    score=score_synthetic_base_correction(proposal,rows)
    assert score['experiment_screen_passed'] is (fault is None)
    assert not score['motion_authorized']
