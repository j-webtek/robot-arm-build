import math
import pytest
from test_wrist_model_correction import fixture
from rocell.application.wrist_model_correction_preview import preview_model_correction
from rocell.motion.observational_wrist_plan import JOINTS
from rocell.application.first_motion_contract import canonical
from rocell.application.wrist_model_correction_preview import verify_model_correction_preview


def inputs(monkeypatch, start=3.779296882):
    raw, args, results = fixture(monkeypatch, start)
    joints = args.pop('start_joints_rad')
    args.update(historical_start_joints_rad=joints,
        samples=[dict(host_received_ns=1_000_000_000+i*50_000_000,
                      joints_rad=dict(zip(JOINTS,joints))) for i in range(5)],
        now_ns=1_200_000_000,
        current_context_references=results['0']['configuration_references'].copy())
    return raw,args


@pytest.mark.parametrize('start', [3.779296882,.966796894])
def test_both_targets_bound_and_no_native_authority(monkeypatch,start):
    raw,args=inputs(monkeypatch,start)
    p=preview_model_correction(raw,**args)
    assert p['nominal_endpoint_rad']==math.radians(2)
    assert p['candidate_command']['rad']!=p['nominal_endpoint_rad']
    assert p['maximum_commands']==1 and not p['automatic_retry']
    assert not p['motion_authorized'] and not p['native_admission_implemented']
    q=preview_model_correction(raw,**args)
    assert p==q
    args['samples'][-1]['joints_rad']['b']+=.001
    q=preview_model_correction(raw,**args)
    assert p['baseline_sha256']!=q['baseline_sha256']


@pytest.mark.parametrize('fault',['old','future','gap','unstable','joint','context','wrong_side'])
def test_reject_changed_or_invalid_baseline(monkeypatch,fault):
    raw,args=inputs(monkeypatch)
    if fault=='old':args['now_ns']+=100_000_001
    if fault=='future':args['now_ns']-=1
    if fault=='gap':args['samples']=args['samples'][::4]
    if fault=='unstable':args['samples'][0]['joints_rad']['t']+=.02
    if fault=='joint':
        for s in args['samples']:s['joints_rad']['b']+=.02
    if fault=='context':args['current_context_references']['workcell_sha256']='changed'
    if fault=='wrong_side':
        for s in args['samples']:s['joints_rad']['t']=0
    with pytest.raises(ValueError):preview_model_correction(raw,**args)


@pytest.mark.parametrize('field',['nominal','command','baseline','authority','unchanged'])
def test_independent_reconstruction_rejects_target_substitution(monkeypatch,field):
    raw,args=inputs(monkeypatch)
    p=preview_model_correction(raw,**args)
    if field=='nominal':p['nominal_endpoint_rad']=p['candidate_command']['rad']
    if field=='command':p['candidate_command']['rad']=p['nominal_endpoint_rad']
    if field=='baseline':p['baseline_sha256']='0'*64
    if field=='authority':p['motion_authorized']=True
    if field=='unchanged':
        result=verify_model_correction_preview(canonical(p),raw,**args)
        assert result['consistent'] and not result['motion_authorized']
    else:
        with pytest.raises(ValueError,match='changed'):
            verify_model_correction_preview(canonical(p),raw,**args)
