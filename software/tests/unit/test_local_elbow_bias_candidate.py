from pathlib import Path
import math
import pytest
from rocell.geometry import UrdfModel
from rocell.application.local_elbow_bias_candidate import build_candidate


@pytest.fixture
def data():
    rows=[]
    for start,wire,end in [(1.762543925,1.7742992981223962,1.779417714),
                           (1.779417714,1.785417714,1.79168956)]:
        baseline=[.001533981,.033747577,start,-.053689328,.018407769,3.138524692]
        final=list(baseline);final[2]=end
        rows.append(dict(command=dict(T=101,joint=3,rad=wire,spd=20,acc=1),
            baseline_joints_rad=baseline,final_joints_rad=final,maximum_other_joint_change_rad=0,
            elbow=dict(ideal_error_rad=end-wire,ideal_delta_deg=math.degrees(wire-start),
                       reported_delta_deg=math.degrees(end-start))))
    model=UrdfModel.from_file(Path(__file__).resolve().parents[3]/
        'software/models/roarm_m3/roarm_m3_kinematic_40dbd84.urdf')
    return model,rows


def test_constant_bias_and_held_out_step(data):
    c=build_candidate(*data)
    assert c['mean_residual_rad']==pytest.approx(.005695130938801918)
    assert c['desired_joints_rad'][2]==pytest.approx(1.80568956)
    assert c['command']['rad']==pytest.approx(1.799994429061198)
    assert c['envelopes']['desired']['maximum_sampled_tip_displacement_mm']<6
    assert not c['prospectively_validated'] and not c['motion_authorized']


@pytest.mark.parametrize('fault',['direction','spread','continuity','settings','other_joint','extrapolation'])
def test_rejects_inadequate_evidence(data,fault):
    model,rows=data
    if fault=='direction':rows[1]['elbow']['reported_delta_deg']=0
    elif fault=='spread':rows[1]['elbow']['ideal_error_rad']=.02
    elif fault=='continuity':rows[1]['baseline_joints_rad'][2]+=.01
    elif fault=='settings':rows[1]['command']['spd']=40
    elif fault=='other_joint':rows[1]['maximum_other_joint_change_rad']=.002
    else:
        for r in rows:r['elbow']['reported_delta_deg']=math.degrees(.01)
    with pytest.raises(ValueError):build_candidate(model,rows)
