"""Synthetic horizon evidence; no serial connection or physical commands."""
import math
import pytest
from rocell.arm.endpoint_persistence import analyze_endpoint_persistence

WRITE = 1_000_000_000
START = [0.] * 6
TARGET = math.radians(1)


def rows(mode='stable'):
    for ms in range(20, 35001, 20):
        pose = [0.] * 6
        pose[4] = TARGET - math.radians(.2)
        if mode in ('late', 'return') and 10000 <= ms < (20000 if mode == 'return' else 40000):
            pose[4] += math.radians(.087890637)
        if mode == 'drift' and ms >= 5000:
            pose[4] += math.radians((ms-5000)/10000)
        if mode == 'other' and ms > 20000:
            pose[1] = math.radians(1)
        if mode == 'gap' and 10000 <= ms <= 11000:
            continue
        yield WRITE + ms*1_000_000 - 1_000_000, WRITE + ms*1_000_000, pose


def analyze(data=None, **kw):
    args = dict(joint='r', start=START, target=TARGET,
                write_finished_ns=WRITE, capture_finished_ns=WRITE+35_000_000_000)
    args.update(kw)
    return analyze_endpoint_persistence(rows() if data is None else data, **args)


@pytest.mark.parametrize('mode,status', [
    ('stable', 'REPORTED_ENDPOINT_PERSISTENT'), ('late', 'REPORTED_ENDPOINT_CHANGED'),
    ('return', 'REPORTED_ENDPOINT_CHANGED'), ('drift', 'ENDPOINT_NOT_VERIFIED'),
    ('other', 'ENDPOINT_NOT_VERIFIED'), ('gap', 'OBSERVATION_INCOMPLETE')])
def test_distinct_outcomes(mode, status):
    result = analyze(rows(mode))
    assert result['status'] == status
    assert not result['motion_authorized'] and not result['automatic_next_command_allowed']
    if mode == 'return':
        assert result['final_minus_early_rad'] == 0
        assert result['maximum_departure_after_5s_rad'] > 0
        assert result['after_5s_transition_count'] == 2


def test_historical_early_result_does_not_change_with_late_step():
    stable, late = analyze(), analyze(rows('late'))
    assert stable['horizons'][0] == late['horizons'][0]
    assert late['horizons'][-1]['final_rad'] != late['horizons'][0]['final_rad']


@pytest.mark.parametrize('fault', ['empty', 'nan', 'backwards', 'too_many', 'shape', 'bool_time'])
def test_bad_rows_never_look_persistent(fault):
    data = list(rows())
    if fault == 'empty': data = []
    if fault == 'nan': data[-1][2][4] = float('nan')
    if fault == 'backwards': data[-1] = data[0]
    if fault == 'too_many': data = [data[0]] * 4097
    if fault == 'shape': data[-1] = (1, 2)
    if fault == 'bool_time': data[-1] = (True, True, START)
    assert analyze(data)['status'] in ('FEEDBACK_INVALID', 'OBSERVATION_INCOMPLETE')


@pytest.mark.parametrize('kw,status', [
    ({'cancelled': True}, 'CANCELLED'),
    ({'transport_clean': False}, 'TRANSPORT_FAULT'),
    ({'capture_issues': ['truncated']}, 'FEEDBACK_INVALID')])
def test_capture_faults_override_steady_rows(kw, status):
    assert analyze(**kw)['status'] == status


def test_only_five_seconds_is_not_persistent_for_thirty_five():
    data = [r for r in rows() if r[1] <= WRITE+5_000_000_000]
    result = analyze(data, capture_finished_ns=WRITE+5_000_000_000)
    assert result['horizons'][0]['endpoint']['endpoint_verified']
    assert result['status'] == 'OBSERVATION_INCOMPLETE'


def test_read_straddling_horizon_is_not_assigned_early():
    data = list(rows())
    i = next(i for i,r in enumerate(data) if r[1] == WRITE+5_000_000_000)
    data[i] = (data[i][0], data[i][1]+1, data[i][2])
    result = analyze(data)
    assert result['horizons'][0]['sample_count'] == 249


@pytest.mark.parametrize('kw', [{'target': float('inf')}, {'joint': 'bad'},
    {'start': [0]}, {'write_finished_ns': True}, {'transport_clean': 1}])
def test_invalid_configuration_rejected(kw):
    with pytest.raises(ValueError): analyze(**kw)


def test_horizon_budget_cannot_be_extended_by_caller():
    with pytest.raises(ValueError): analyze(capture_finished_ns=WRITE+36_000_000_000)


@pytest.mark.parametrize('axis', [0, 1, 2, 3, 5])
def test_each_other_joint_is_checked_across_long_window(axis):
    data = list(rows())
    data[-1][2][axis] += math.radians(1)
    assert analyze(data)['status'] == 'ENDPOINT_NOT_VERIFIED'


def test_transition_display_does_not_grow_without_limit():
    data = list(rows())
    for i, row in enumerate(data):
        if row[0] > WRITE+5_000_000_000:
            row[2][4] += math.radians(.02) * (i % 2)
    result = analyze(data)
    assert len(result['first_transitions']) == 16
    assert result['transition_display_truncated']
    assert result['status'] == 'REPORTED_ENDPOINT_CHANGED'
