import copy
import math

import pytest

from rocell.motion.observational_wrist_plan import preview_observational_wrist


def capture():
    return [{'host_received_ns': 1_000_000_000 + i * 50_000_000,
             'joints_rad': dict(b=0., s=0., e=1.57, t=.02, r=0., g=3.14)}
            for i in range(5)]


@pytest.mark.parametrize('direction', [-1, 1])
def test_increment_is_converted_to_absolute_without_measurements(direction):
    samples = capture()
    original = copy.deepcopy(samples)
    result = preview_observational_wrist(samples=samples, now_ns=1_300_000_000,
                                        direction=direction)
    assert result['candidate_command'] == dict(T=101, joint=4,
        rad=.02 + direction * math.radians(1), spd=20, acc=1)
    assert result['precision_measurements_required'] is False
    assert result['motion_authorized'] is False
    assert result['device_sample_freshness_verified'] is False
    assert samples == original


@pytest.mark.parametrize('fault', ['stale', 'future', 'backward', 'gap', 'unstable',
    'nonfinite', 'bool', 'missing_joint', 'extra_field', 'outside', 'target_outside',
    'too_short', 'too_many'])
def test_rejects_unsuitable_capture(fault):
    samples, now = capture(), 1_300_000_000
    if fault == 'stale': now = 4_000_000_000
    if fault == 'future': now = 1_100_000_000
    if fault == 'backward': samples[1]['host_received_ns'] = samples[0]['host_received_ns'] - 1
    if fault == 'gap': samples = [samples[0], samples[-1]]
    if fault == 'unstable': samples[-1]['joints_rad']['b'] = .1
    if fault == 'nonfinite': samples[-1]['joints_rad']['t'] = float('nan')
    if fault == 'bool': samples[-1]['joints_rad']['t'] = True
    if fault == 'missing_joint': del samples[-1]['joints_rad']['g']
    if fault == 'extra_field': samples[0]['approved'] = True
    if fault in ('outside', 'target_outside'):
        for sample in samples:
            sample['joints_rad']['t'] = math.radians(-20 if fault == 'outside' else -9.5)
    if fault == 'too_short': samples = samples[:2]
    if fault == 'too_many': samples = samples * 52
    with pytest.raises(ValueError):
        preview_observational_wrist(samples=samples, now_ns=now)


@pytest.mark.parametrize('direction', [True, 0, 2, 1., '1'])
def test_rejects_unbounded_direction(direction):
    with pytest.raises(ValueError):
        preview_observational_wrist(samples=capture(), now_ns=1_300_000_000,
                                   direction=direction)


def test_baseline_hash_changes_with_evidence():
    samples = capture()
    first = preview_observational_wrist(samples=samples, now_ns=1_300_000_000)
    samples[0]['joints_rad']['b'] = .001
    second = preview_observational_wrist(samples=samples, now_ns=1_300_000_000)
    assert first['baseline_sha256'] != second['baseline_sha256']
