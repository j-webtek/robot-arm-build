import pytest
from rocell.application.coordinated_affine_trial import supported_inverse


def model():
    return dict(joint='elbow',slope=.5,intercept_deg=.6)


def rows():
    return [dict(elbow=dict(requested_delta_deg=x,reported_delta_deg=.5*x+.6)) for x in (.4,.8)]


def test_interior_inverse():
    assert supported_inverse(model(),rows(),.9)==pytest.approx(.6)


@pytest.mark.parametrize('target',[.5,.8,1.,1.2,float('nan'),True])
def test_extrapolation_boundaries_and_nonfinite_rejected(target):
    with pytest.raises(ValueError):supported_inverse(model(),rows(),target)


@pytest.mark.parametrize('slope',[0,-1,float('inf')])
def test_invalid_response_slope_rejected(slope):
    c=model();c['slope']=slope
    with pytest.raises(ValueError):supported_inverse(c,rows(),.9)
