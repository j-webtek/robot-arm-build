import math
from copy import deepcopy
import pytest
from rocell.arm.joint_endpoint_verification import JOINT_KEYS, verify_reported_joint
from rocell.application.joint_bias_experiments import fit_synthetic_joint_bias


def trial(joint,direction,index,bias=None):
    axis=JOINT_KEYS.index(joint)
    target=math.radians(5*axis)
    start=[0.]*6
    start[axis]=target-math.radians(direction*1.5)
    # Deliberately distinct per-axis biases prevent accidental wrist reuse.
    error=math.radians(-direction*(.2+.05*axis)) if bias is None else math.radians(bias)
    rows=[]
    for tick in range(1,251):
        joints=start.copy()
        joints[axis]=start[axis]+(target+error-start[axis])*min(tick/50,1)
        stamp=1_000_000_000+tick*20_000_000
        rows.append((stamp,stamp,joints))
    return dict(id=f'{joint}-{direction}-{index}',split='train' if index<3 else 'validation',
        joint=joint,start_rad=start,target_rad=target,command_rad=target,rows=rows,
        context='fixture-unchanged-tool-pose',spd=20,acc=1)


def trials():
    return [trial(j,d,n) for j in JOINT_KEYS for d in (-1,1) for n in range(5)]


@pytest.mark.parametrize('joint',JOINT_KEYS)
def test_selected_axis_arrival_and_other_axis_drift(joint):
    t=trial(joint,1,0,bias=0)
    args=dict(joint=joint,start=t['start_rad'],target=t['target_rad'])
    result=verify_reported_joint(t['rows'],**args)
    assert result['endpoint_verified'] and result['joint']==joint
    other=(JOINT_KEYS.index(joint)+1)%6
    t['rows'][-1][2][other]+=math.radians(1)
    result=verify_reported_joint(t['rows'],**args)
    assert result['status']=='OTHER_JOINT_CHANGED' and not result['endpoint_verified']


def test_all_axes_fit_distinct_local_direction_models_without_authority():
    result=fit_synthetic_joint_bias(trials())
    assert len(result['models'])==12
    for model in result['models']:
        sign=1 if model['direction']=='DECREASING' else -1
        expected=math.radians(sign*(.2+.05*JOINT_KEYS.index(model['joint'])))
        assert model['bias_rad']==pytest.approx(expected)
        assert model['offline_prediction_screen_passed']
        assert model['prediction_mae_rad']==pytest.approx(0)
        assert set(model['train_ids']).isdisjoint(model['validation_ids'])
    assert not result['motion_authorized'] and not result['compensation_enabled']


@pytest.mark.parametrize('fault',['duplicate','gap','short','drift','command','speed','pose','few','badrow'])
def test_unusable_trials_cannot_train(fault):
    data=trials();t=data[0]
    if fault=='duplicate':data[1]=deepcopy(t)
    if fault=='gap':t['rows']=t['rows'][:50]+t['rows'][70:]
    if fault=='short':t['rows']=t['rows'][:100]
    if fault=='drift':t['rows'][-1][2][1]=math.radians(1)
    if fault=='command':t['command_rad']+=.001
    if fault=='speed':t['spd']=40
    if fault=='pose':
        t['start_rad'][1]=math.radians(1)
        for row in t['rows']:row[2][1]=math.radians(1)
    if fault=='few':data.pop(0)
    if fault=='badrow':t['rows'][100]=(0,0,[])
    with pytest.raises(ValueError):fit_synthetic_joint_bias(data)


def test_unseen_direction_error_does_not_pass_validation():
    data=trials()
    data[3]=trial('b',-1,3,bias=.8)
    result=fit_synthetic_joint_bias(data)
    assert not next(m for m in result['models'] if m['joint']=='b' and m['direction']=='DECREASING')['offline_prediction_screen_passed']


def test_wrist_adapter_matches_original_monitor_without_changing_old_schema():
    from rocell.arm.wrist_endpoint_verification import verify_reported_wrist
    t=trial('t',-1,0)
    old=verify_reported_wrist(t['rows'],start=t['start_rad'],target=t['target_rad'],capture_issues=(),transport_clean=True)
    new=verify_reported_joint(t['rows'],joint='t',start=t['start_rad'],target=t['target_rad'])
    assert old['endpoint_verified']==new['endpoint_verified']
    assert old['final_error_rad']==new['final_error_rad']
    assert old['schema']=='rocell.reported_wrist_endpoint.v1'
