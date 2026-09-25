from copy import deepcopy
import math
import pytest
from rocell.application.controller_route_preview import preview_vertical_pair, preview_elbow_isolation
from rocell.kinematics.firmware_reference import forward


def baseline():
    joints = dict(b=-.001533981,s=0,e=1.593806039,t=.007669904,r=.021475731,g=3.149262558)
    return dict(status='SUCCEEDED',identity_before_matched=True,identity_after_matched=True,
        joints_rad=joints,controller_cartesian=dict(values=dict(zip(('x','y','z','tit'),
            forward(*(joints[k] for k in ('b','s','e','t')))))))


def test_two_leg_preview_preserves_endpoints_and_does_not_mutate():
    original=baseline(); before=deepcopy(original)
    report=preview_vertical_pair(original)
    assert original==before
    assert report['status']=='PREVIEW_ONLY_NOT_EXECUTABLE'
    assert len(report['legs'])==2
    assert all(len(leg['samples'])==41 for leg in report['legs'])
    assert report['legs'][0]['samples'][-1]['target_xyz_pitch'][2]==report['starting_pose'][2]+2
    assert report['legs'][1]['samples'][-1]['target_xyz_pitch']==report['starting_pose']
    assert all(s['accepted'] for leg in report['legs'] for s in leg['samples'])
    assert max(report['maximum_joint_change_deg']) < 1
    assert report['command_count']==0 and not report['motion_authorized']
    assert not report['full_arm_clearance_verified'] and not report['timing_simulated']


def test_reference_mismatch_has_no_route():
    report=baseline(); report['controller_cartesian']['values']['z']+=1
    result=preview_vertical_pair(report)
    assert result['status']=='REFERENCE_MISMATCH' and not result['legs']


@pytest.mark.parametrize('field', ['x','y','z','tit'])
def test_missing_cartesian_cannot_be_zero_filled(field):
    report=baseline(); del report['controller_cartesian']['values'][field]
    with pytest.raises(ValueError): preview_vertical_pair(report)


@pytest.mark.parametrize('value',[True,None,float('nan'),float('inf')])
def test_invalid_joint_cannot_generate_route(value):
    report=baseline(); report['joints_rad']['s']=value
    with pytest.raises(ValueError): preview_vertical_pair(report)


def test_identity_failure_rejected():
    report=baseline(); report['identity_after_matched']=False
    with pytest.raises(ValueError): preview_vertical_pair(report)


def test_larger_diagnostic_preserves_existing_joint_excursion_limit():
    report=preview_vertical_pair(baseline(),step_mm=5)
    assert report['status']=='PREVIEW_ONLY_NOT_EXECUTABLE'
    assert report['step_mm']==5
    assert report['legs'][0]['samples'][-1]['target_xyz_pitch'][2]==report['starting_pose'][2]+5
    assert max(report['maximum_joint_change_deg'])<3


@pytest.mark.parametrize('step',[True,0,-2,3,10,5.0])
def test_no_arbitrary_diagnostic_step(step):
    with pytest.raises(ValueError):preview_vertical_pair(baseline(),step_mm=step)


def test_elbow_preview_does_not_change_other_joints():
    original=baseline()
    result=preview_elbow_isolation(original)
    assert result['status']=='PREVIEW_ONLY_NOT_EXECUTABLE'
    assert len(result['samples'])==41
    initial=[original['joints_rad'][k] for k in ('b','s','e','t','r','g')]
    assert result['target_joints_rad'][2]==initial[2]-math.radians(2)
    for i in (0,1,3,4,5):assert result['target_joints_rad'][i]==initial[i]
    assert math.dist(result['target_pose'][:3],result['starting_pose'][:3])<=15
    assert not result['motion_authorized']


def test_elbow_preview_rejects_reference_mismatch():
    original=baseline()
    original['controller_cartesian']['values']['z']+=1
    assert preview_elbow_isolation(original)['status']=='REFERENCE_MISMATCH'
