from pathlib import Path
import pytest
from rocell.application.controller_model_baseline import compare_controller_model, ARM_MAP
from rocell.geometry import load_urdf, JointPosition

ROOT = Path(__file__).resolve().parents[3]


def sample():
    return dict(status='SUCCEEDED', identity_before_matched=True, identity_after_matched=True,
        joints_rad=dict(b=0,s=0,e=1.5,t=0,r=0,g=3.149262558),
        controller_cartesian=dict(values=dict(x=340,y=0,z=214,tit=0)))


@pytest.fixture
def model():
    return load_urdf(ROOT/'software/models/roarm_m3/roarm_m3_kinematic_40dbd84.urdf')


def test_ancestor_chain_matches_full_fk_and_does_not_use_gripper(model):
    report = sample()
    result = compare_controller_model(report, model)
    positions = {name:JointPosition.radians(report['joints_rad'][key]) for key,name in ARM_MAP}
    positions['link5_to_gripper_link'] = JointPosition.radians(0)
    point = model.forward_kinematics(positions)['hand_tcp'].translation_mm
    assert result['vendor_world_hand_tcp_mm'] == pytest.approx([point.x,point.y,point.z])
    report['joints_rad']['g'] = 0.5
    assert compare_controller_model(report,model)['vendor_world_hand_tcp_mm'] == result['vendor_world_hand_tcp_mm']
    assert not result['calibration_produced'] and not result['motion_authorized']
    assert not result['controller_model_correlation_verified']


def test_absent_cartesian_does_not_produce_offset(model):
    report = sample()
    report.pop('controller_cartesian')
    result = compare_controller_model(report, model)
    assert result['controller_xyz_mm'] == [None,None,None]
    assert result['hypothetical_frame_equivalence_residual_mm'] is None


@pytest.mark.parametrize('key', ['identity_before_matched','identity_after_matched'])
def test_unmatched_identity_rejected(model,key):
    report = sample()
    report[key] = False
    with pytest.raises(ValueError):
        compare_controller_model(report, model)


@pytest.mark.parametrize('value', [True,float('nan'),float('inf')])
def test_invalid_joint_rejected(model,value):
    report = sample()
    report['joints_rad']['s'] = value
    with pytest.raises(ValueError):
        compare_controller_model(report,model)
