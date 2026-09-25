"""Endpoint-only evidence is explicitly weaker than continuous observation."""

import pytest

from rocell.arm.movement_analysis import analyze_endpoint_trial, analyze_trial
from rocell.motion.characterization_plan import freeze_campaign
from test_characterization_plan import candidate
from test_movement_analysis import wire, EPOCH


def endpoints(values=None, times=None):
    values = [1]*13 if values is None else values
    times = [800_000_000+i*50_000_000 for i in range(len(values))] if times is None else times
    raw, windows = wire(values, times)
    return raw, windows, dict(command_completed_ns=EPOCH, observation_end_ns=windows[-1][3],
                              basis='SYNTHETIC_WIRE_REHEARSAL')


def test_delayed_feedback_can_establish_endpoint_dwell_not_continuous_motion():
    raw, windows, kw = endpoints()
    plan = freeze_campaign(candidate())
    continuous = analyze_trial(plan, 'out', raw, windows, **kw)
    endpoint = analyze_endpoint_trial(plan, 'out', raw, windows, **kw)
    assert 'READ_COVERAGE_GAP' in continuous['issues']
    assert continuous['status'] == 'INSUFFICIENT_EVIDENCE'
    assert endpoint['status'] == 'OBSERVED_ENDPOINT_DWELL'
    assert endpoint['initial_unobserved_interval_ns'] == [EPOCH, EPOCH+800_000_000]
    assert endpoint['host_endpoint_dwell_entry_bounds_ns'] == [800_000_000,801_000_000]
    assert endpoint['peak_observed_directional_overshoot_mm'] is None
    assert endpoint['travel_time_s'] is None
    assert endpoint['host_settling_entry_bounds_ns'] is None
    assert not endpoint['continuous_motion_observation']
    assert not endpoint['physical_stop_verified']


@pytest.mark.parametrize('values', [[1], [0]*13, [1]*12+[.5]])
def test_single_sample_unchanged_and_departure_are_not_endpoint_dwell(values):
    raw, windows, kw = endpoints(values)
    result = analyze_endpoint_trial(freeze_campaign(candidate()), 'out', raw, windows, **kw)
    assert result['status'] == 'INSUFFICIENT_ENDPOINT_EVIDENCE'
    assert result['host_endpoint_dwell_entry_bounds_ns'] is None


def test_gap_after_feedback_begins_is_not_excused_by_endpoint_contract():
    times = [800_000_000+i*50_000_000+(200_000_000 if i>=5 else 0) for i in range(13)]
    raw, windows, kw = endpoints(times=times)
    result = analyze_endpoint_trial(freeze_campaign(candidate()), 'out', raw, windows, **kw)
    assert 'READ_COVERAGE_GAP' in result['issues']
    assert result['status'] == 'INSUFFICIENT_ENDPOINT_EVIDENCE'


def test_late_reply_does_not_extend_trial_timeout():
    raw, windows, kw = endpoints(times=[2_100_000_000+i*50_000_000 for i in range(13)])
    result = analyze_endpoint_trial(freeze_campaign(candidate()), 'out', raw, windows, **kw)
    assert result['latest_reported_endpoint'] is None
    assert result['initial_unobserved_interval_ns'] is None
    assert result['status'] == 'INSUFFICIENT_ENDPOINT_EVIDENCE'


def test_shared_host_read_cannot_establish_dwell():
    raw, windows, kw = endpoints()
    # Retain byte-sized read segments but give every segment the same host time.
    # Multiple buffered lines must not manufacture elapsed dwell.
    for row in windows:
        row[2:] = [EPOCH+800_000_000, EPOCH+800_000_000]
    kw['observation_end_ns'] = EPOCH+800_000_001
    result = analyze_endpoint_trial(freeze_campaign(candidate()), 'out', raw, windows, **kw)
    assert result['status'] == 'INSUFFICIENT_ENDPOINT_EVIDENCE'
