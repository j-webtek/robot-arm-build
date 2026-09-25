import math
import pytest
from rocell.kinematics.firmware_reference import servo_goals, feedback_counts, joint_response_comparison


def test_reference_midpoint_asymmetry_is_explicit():
    assert servo_goals([0,0,0,0,0,math.pi]) == dict(
        b=2047,s=2047,s_follower=2047,e=1024,t=2047,r=2047,g=2048)
    assert feedback_counts([0,0,0,0,0,math.pi]) == dict(
        b=2048,s=2048,e=1024,t=2048,r=2048,g=2048)


def test_cpp_half_rounding_and_clamps():
    half_tick=math.pi/4096
    goals=servo_goals([half_tick,half_tick,0,-half_tick,half_tick,0])
    assert goals['b']==2046 and goals['s']==2048
    assert goals['s_follower']==2046 and goals['t']==2046
    assert goals['r']==2046 and goals['g']==700
    assert servo_goals([0,0,math.pi,0,0,2*math.pi])['e']==3071


def test_retained_live_miss_is_not_explained_by_one_count_rounding():
    baseline=[-.001533981,0,1.593806039,.007669904,.021475731,3.149262558]
    expected=[-.001533980787,-.000135718598,1.5801262316,.021485429794,.021475731,3.149262558]
    reported=[-.001533981,0,1.593806039,.01994175,.021475731,3.149262558]
    rows={r['joint']:r for r in joint_response_comparison(baseline,expected,reported)}
    assert rows['e']['predicted_count_change']==-9
    assert rows['e']['reported_count_change']==0
    assert rows['e']['count_error']==9
    assert rows['t']['predicted_count_change']==8
    assert rows['t']['reported_count_change']==8
    assert rows['t']['count_error']==0


@pytest.mark.parametrize('value',[True,float('nan'),float('inf')])
def test_bad_angles_rejected(value):
    with pytest.raises(ValueError):servo_goals([value,0,0,0,0,3])
    with pytest.raises(ValueError):feedback_counts([value,0,0,0,0,3])
