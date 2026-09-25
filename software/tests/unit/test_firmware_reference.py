"""Numerical reference tests, not evidence of physical positional accuracy."""
import itertools
import math
import pytest
from rocell.kinematics.firmware_reference import forward, inverse


def test_saved_controller_snapshot_matches_reference_rounding():
    actual = forward(-.001533981, 0, 1.593806039, .007669904)
    assert actual[:3] == pytest.approx((345.6206222, -.53017581, 214.5461189), abs=2e-7)
    assert actual[3] == pytest.approx(.030679616, abs=3e-10)


@pytest.mark.parametrize('base,shoulder,elbow', list(itertools.product(
    (-.2,0,.2), (-.1,0,.1), (1.4,1.5,1.6))))
def test_regular_branch_roundtrip(base,shoulder,elbow):
    pose = forward(base,shoulder,elbow,.02)
    recovered = forward(*inverse(*pose))
    assert math.dist(pose[:3],recovered[:3]) < 1e-9
    assert abs(pose[3]-recovered[3]) < 1e-12


@pytest.mark.parametrize('value', [True, float('nan'), float('inf'), '0'])
def test_invalid_inputs_rejected(value):
    with pytest.raises(ValueError): forward(value,0,1.5,0)
    with pytest.raises(ValueError): inverse(value,0,200,0)
