import math
import pytest
from rocell.arm.joint_mapping import JOINT_MAP, mapping_for, reference_joint_goal, preview_mapping_probe, STEP_RAD


def test_reference_map_matches_telemetry_order_and_separate_bus_ids():
    assert [m.key for m in JOINT_MAP]==list('bsetrg')
    assert [m.command_id for m in JOINT_MAP]==list(range(1,7))
    assert mapping_for('s').servo_ids==(12,13)


@pytest.mark.parametrize('key,angle,goal,error',[
    ('b',0,2047,1),('s',0,2047,-1),('e',math.pi/2,2048,0),
    ('t',0,2047,-1),('r',0,2047,1),('g',math.pi,2048,0)])
def test_reference_centers_and_feedback_offsets(key,angle,goal,error):
    p=reference_joint_goal(key,angle)
    assert p['goal_registers'][0]==goal
    assert p['reference_feedback_error_rad']==pytest.approx(error*STEP_RAD)
    assert not p['motion_authorized'] and not p['installed_firmware_verified']


def test_opposite_servo_directions_and_dual_shoulder():
    assert reference_joint_goal('b',.1)['goal_registers'][0]<2047
    assert reference_joint_goal('r',.1)['goal_registers'][0]<2047
    assert reference_joint_goal('t',.1)['goal_registers'][0]>2047
    a,b=reference_joint_goal('s',.1)['goal_registers']
    assert a>2047>b and a+b==4094


@pytest.mark.parametrize('joint',JOINT_MAP)
def test_probe_binds_correct_axis_without_compensation(joint):
    start=[0,0,math.pi/2,0,0,math.pi]
    p=preview_mapping_probe(joint.key,start_rad=start,delta_deg=1)
    assert p['candidate_command']['joint']==joint.command_id
    assert p['candidate_command']['rad']==p['nominal_target_rad']
    assert p['nominal_target_rad']==pytest.approx(start[joint.telemetry_index]+math.radians(1))
    assert not p['motion_authorized'] and not p['compensation_applied']


@pytest.mark.parametrize('key,target',[('s',math.pi),('t',math.pi),('e',-.1),('g',0)])
def test_reference_clamping_is_visible_not_a_safety_approval(key,target):
    assert reference_joint_goal(key,target)['clamped']


@pytest.mark.parametrize('delta',[True,0,.5,3,float('nan')])
def test_unbounded_probe_rejected(delta):
    with pytest.raises(ValueError):preview_mapping_probe('b',start_rad=[0.]*6,delta_deg=delta)


def test_unsafe_reference_edge_rejected():
    with pytest.raises(ValueError):preview_mapping_probe('b',start_rad=[math.pi,0,0,0,0,0],delta_deg=1)
    with pytest.raises(ValueError):mapping_for(1)


def test_wrist_prediction_agrees_with_existing_reference_model():
    from rocell.application.wrist_accuracy_analysis import reference_wrist_goal
    for angle in (-.1,0,.1):
        assert reference_joint_goal('t',angle)['predicted_feedback_rad']==reference_wrist_goal(angle)['representable_rad']
