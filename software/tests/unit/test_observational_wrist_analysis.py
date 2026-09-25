import math

import pytest

from rocell.arm.observational_wrist_analysis import (
    preview_from_capture, assess_observational_response,
)
from test_first_motion_analysis import wire


def evaluate(**overrides):
    start = .02
    before, bw = wire([start] * 10, 2_000_000_000)
    target = start - math.radians(1)
    after, aw = wire(overrides.pop('values', [target] * 10), 2_500_000_002,
                     corrupt_at=overrides.pop('corrupt_at', None),
                     other_at=overrides.pop('other_at', None))
    kwargs = dict(baseline_started_ns=2_000_000_000,
        baseline_finished_ns=2_500_000_000, write_started_ns=2_500_000_000,
        write_finished_ns=2_500_000_001, observation_end_ns=3_000_000_000,
        direction=-1, actual_command=dict(T=101, joint=4, rad=target, spd=20, acc=1),
        operator_outcome='EXPECTED_MOVEMENT',
        operator_covered_trial=True, transport_clean=True, basis='SYNTHETIC_WIRE_REHEARSAL')
    kwargs.update(overrides)
    return assess_observational_response(before, bw, after, aw, **kwargs)


def test_functional_pass_does_not_require_precision_or_grant_motion():
    result = evaluate()
    assert result['status'] == 'SYNTHETIC_FUNCTIONAL_PASS'
    assert result['reported_final_error_rad'] == 0
    assert result['issues'] == []
    assert result['physical_accuracy_verified'] is False
    assert result['motion_authorized'] is False
    assert result['campaign_advance_allowed'] is False


@pytest.mark.parametrize('change,issue', [
    ({'values': [.02] * 10}, 'NO_RESOLVABLE_REPORTED_WRIST_CHANGE'),
    ({'corrupt_at': 3}, 'POST_INVALID_JOINT_RECORD'),
    ({'other_at': 4}, 'OTHER_REPORTED_JOINT_CHANGED'),
    ({'values': [.5] * 10}, 'REPORTED_WRIST_EXCURSION'),
    ({'operator_outcome': 'NO_MOVEMENT'}, 'OPERATOR_RESPONSE_NOT_EXPECTED'),
    ({'operator_outcome': 'WRONG_MOVEMENT'}, 'OPERATOR_RESPONSE_NOT_EXPECTED'),
    ({'operator_outcome': 'UNKNOWN'}, 'OPERATOR_RESPONSE_NOT_EXPECTED'),
    ({'operator_covered_trial': False}, 'OPERATOR_COVERAGE_INCOMPLETE'),
    ({'transport_clean': False}, 'TRANSPORT_OR_CLEANUP_FAULT'),
])
def test_conflicts_hold_instead_of_hiding_bad_frames(change, issue):
    result = evaluate(**change)
    assert result['status'] == 'HELD'
    assert issue in result['issues']


def test_shared_read_timestamps_do_not_discard_frames():
    raw, windows = wire([.02] * 10, 2_000_000_000)
    # Two records have the same host acquisition bounds, as with a shared read.
    windows[0][1] = windows[1][1]
    del windows[1]
    result = preview_from_capture(raw, windows, started_ns=2_000_000_000,
        finished_ns=2_500_000_000, now_ns=2_500_000_000)
    assert result['sample_count'] == 10


def test_one_batched_read_cannot_prove_a_stable_time_span():
    raw, windows = wire([.02] * 10, 2_000_000_000)
    for row in windows: row[2:] = [2_000_000_000, 2_000_000_000]
    with pytest.raises(ValueError):
        preview_from_capture(raw, windows, started_ns=2_000_000_000,
            finished_ns=2_100_000_000, now_ns=2_100_000_000)


def test_internal_malformed_frame_rejects_preview():
    raw, windows = wire([.02] * 10, 2_000_000_000, corrupt_at=3)
    with pytest.raises(ValueError, match='INVALID_JOINT_RECORD'):
        preview_from_capture(raw, windows, started_ns=2_000_000_000,
            finished_ns=2_500_000_000, now_ns=2_500_000_000)


@pytest.mark.parametrize('command', [dict(T=101, joint=4, rad=0, spd=20, acc=1),
    dict(T=101, joint=4, rad=.02-math.radians(1), spd=0, acc=1),
    dict(T=101, joint=5, rad=.02-math.radians(1), spd=20, acc=1)])
def test_dispatched_command_must_match_baseline_candidate(command):
    with pytest.raises(ValueError, match='Dispatched command differs'):
        evaluate(actual_command=command)
