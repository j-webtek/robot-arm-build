"""Offline reference arithmetic tests, not installed-arm qualification."""
import importlib.util
import math
from pathlib import Path

import pytest

path = Path(__file__).resolve().parents[2]/'scripts/bench_reference_kinematics.py'
spec = importlib.util.spec_from_file_location('bench_reference_kinematics', path)
model = importlib.util.module_from_spec(spec)
spec.loader.exec_module(model)


def baseline():
    values = dict(x=347.3156446, y=-3.196743424, z=207.4284741,
                  tit=.046019424, b=-.009203885, s=.009203885,
                  e=1.613747789, t=-.006135923)
    return {'observed_axis_ranges': {k:[v,v] for k,v in values.items()},
            'source_outcome_sha256': 'a'*64}


def test_reference_matches_reported_pose_without_claiming_physical_accuracy():
    result = model.review(baseline())
    assert result['fk_position_residual_mm'] < 1e-6
    assert result['fk_pitch_residual_rad'] < 1e-8
    assert len(result['samples']) == 41
    assert max(s['roundtrip_position_error_mm'] for s in result['samples']) < 1e-9
    assert max(result['max_sampled_joint_change_deg']) < .8
    for name in ('motion_authorized', 'physical_accuracy_verified',
                 'device_sample_freshness_verified', 'installed_binary_verified',
                 'full_link_and_cable_clearance_verified'):
        assert result[name] is False


@pytest.mark.parametrize('value', [True, float('nan'), float('inf'), 1e7])
def test_invalid_axes_refused(value):
    document = baseline()
    document['observed_axis_ranges']['x'] = [value, value]
    with pytest.raises(ValueError):
        model.review(document)


def test_variable_capture_not_silently_replaced_with_latest():
    document = baseline()
    document['observed_axis_ranges']['z'][1] += 1
    with pytest.raises(ValueError):
        model.review(document)


def test_unreachable_target_not_clamped():
    with pytest.raises(ValueError):
        model.inverse(10000, 0, 10000, 0)


def test_fk_ik_roundtrip_on_regular_near_startup_branch():
    for shoulder in (-.02, 0, .02):
        for elbow in (1.55, 1.57, 1.59):
            joints = (.1, shoulder, elbow, .02)
            actual = model.inverse(*model.forward(*joints))
            assert math.dist(joints, actual) < 1e-12
