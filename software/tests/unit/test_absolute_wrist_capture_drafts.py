"""Historical byte reconstruction, not current pose or live authority."""
import copy
import math

import pytest

from rocell.application.absolute_wrist_capture_drafts import draft_choices_from_capture
from rocell.arm.telemetry_stream import TelemetryStream, compact_capture
from test_observational_capture_preview import observation
from test_first_motion_analysis import wire


def test_choices_freeze_six_joint_start_without_renewing_time():
    original = observation()
    saved = copy.deepcopy(original)
    result = draft_choices_from_capture(original)
    assert original == saved
    assert [item['draft']['target_deg'] for item in result['choices']] == [0, 4]
    assert [item['target_deg'] for item in result['held_targets']] == [-4]
    assert result['captured_end_ns'] == original['observation_finished_monotonic_ns']
    assert result['historical_only'] and result['fresh_owned_baseline_required']
    assert not result['motion_authorized']
    for choice in result['choices']:
        assert len(choice['draft']['expected_start_joints_rad']) == 6
        assert choice['draft']['expected_start_joints_rad']['t'] == .02


@pytest.mark.parametrize('fault', ['early_corruption', 'hash', 'length', 'unstable', 'all_targets_outside'])
def test_bad_capture_or_out_of_range_targets_not_silently_selected(fault):
    value = observation(corrupt_at=3 if fault == 'early_corruption' else None)
    if fault == 'hash': value['capture']['raw']['sha256'] = 'a'*64
    if fault == 'length': value['capture']['raw']['bytes'] += 1
    if fault in ('unstable', 'all_targets_outside'):
        angles = [math.radians(10)]*100 if fault == 'all_targets_outside' else [.02]*99+[.04]
        raw, windows = wire(angles, 2_000_000_000)
        parser = TelemetryStream()
        parser.feed(raw)
        value['capture'] = compact_capture(parser.finish())
        value['read_windows'] = windows
    if fault == 'all_targets_outside':
        result = draft_choices_from_capture(value)
        assert result['choices'] == [] and len(result['held_targets']) == 3
    else:
        with pytest.raises(ValueError): draft_choices_from_capture(value)
