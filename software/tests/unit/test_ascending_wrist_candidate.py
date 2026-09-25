from pathlib import Path
import math
import pytest
from rocell.geometry import UrdfModel
from rocell.application.ascending_wrist_candidate import (
    COUNT_RAD,evaluate_count_normalization,preview_candidate)


@pytest.fixture
def model():
    return UrdfModel.from_file(Path(__file__).resolve().parents[3]/
        'software/models/roarm_m3/roarm_m3_kinematic_40dbd84.urdf')


def test_candidate_separates_wire_and_desired(model):
    start=[.001533981,.033747577,1.762543925,-.055223308,.018407769,3.138524692]
    candidate=preview_candidate(model,start)
    assert candidate['desired_joints_rad'][3]==-.045
    assert candidate['command']['rad']==pytest.approx(-.045+2*math.pi/4096)
    assert candidate['preview']['maximum_sampled_tip_displacement_mm']==pytest.approx(2.71879491397)
    assert not candidate['motion_authorized']
    assert start[3]==-.055223308


def test_correction_does_not_fit_observed_residuals(model):
    def row(residual):
        start=[0,0,1.76,-.065,0,3.14];final=list(start);final[3]=-.05+residual
        return dict(command=dict(T=101,joint=4,rad=-.05,spd=20,acc=1),
            wrist=dict(ideal_delta_deg=.8,reported_delta_deg=.6,ideal_error_rad=residual),
            maximum_other_joint_change_rad=0,baseline_joints_rad=start,final_joints_rad=final)
    result=evaluate_count_normalization(model,[row(-.001),row(-.003)])
    assert result['correction_rad']==COUNT_RAD
    assert result['comparisons'][1]['counterfactual_corrected_residual_rad']==pytest.approx(-.003+COUNT_RAD)
    assert not result['prospectively_validated']
    bad=row(-.003);bad['wrist']['reported_delta_deg']=0
    with pytest.raises(ValueError):evaluate_count_normalization(model,[row(-.001),bad])


def test_large_or_wrong_direction_candidate_rejected(model):
    for wrist in (-.10,0):
        with pytest.raises(ValueError):preview_candidate(model,[0,0,1.76,wrist,0,3.14])
