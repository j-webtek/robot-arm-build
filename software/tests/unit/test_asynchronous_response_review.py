from pathlib import Path
import pytest
from rocell.geometry import UrdfModel
from rocell.application.asynchronous_response_review import review_response_envelope


def test_retained_candidate_has_insufficient_joint_skew_margin():
    model=UrdfModel.from_file(Path(__file__).resolve().parents[3]/'software/models/roarm_m3/roarm_m3_kinematic_40dbd84.urdf')
    start=[.001533981,.033747577,1.725728386,-.064427193,.018407769,3.138524692]
    end=list(start);end[2]=1.7429089706;end[3]=-.0696427276
    nominal=review_response_envelope(model,start,end)
    stress=review_response_envelope(model,start,end,extra_steps=1)
    assert nominal['maximum_sampled_tip_displacement_mm']==pytest.approx(5.792717791)
    assert nominal['status']=='NO_SAMPLED_EXCEEDANCE'
    assert stress['status']=='SAMPLED_MODEL_BOUND_EXCEEDED'
    assert stress['maximum_sampled_tip_displacement_mm']==pytest.approx(6.309910267)
    assert stress['worst_sample_joints_rad'][3]==start[3]
    assert not stress['motion_authorized'] and not stress['continuous_bound_verified']
    assert start[2]==1.725728386  # Inputs not mutated.


@pytest.mark.parametrize('steps',[-1,3,True,.5])
def test_invalid_stress_scope_rejected(steps):
    with pytest.raises(ValueError):review_response_envelope(None,[],[],extra_steps=steps)
