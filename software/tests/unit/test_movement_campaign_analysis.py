"""Campaign comparison uses retained wire originals, not cached success flags."""

from copy import deepcopy

import pytest

from rocell.arm.movement_campaign_analysis import summarize_campaign
from rocell.motion.characterization_plan import freeze_campaign
from rocell.motion.characterization_sim import simulate_campaign
from rocell.motion.characterization_wire_sim import analyze_synthetic_trial
from test_characterization_plan import candidate


def repeated_plan():
    data = candidate()
    pair = data['trials']
    data['trials'] = []
    data['limits'].update(max_trials=16, max_duration_s=40)
    for tier, speed in enumerate((.05, .1)):
        for repeat in range(3):
            for original in pair:
                row = deepcopy(original)
                row.update(trial_id=f'{tier}-{repeat}-{original["trial_id"]}', spd=speed)
                data['trials'].append(row)
    return freeze_campaign(data)


def observations(plan, faults=None):
    simulation = simulate_campaign(plan, travel_s=.5, sample_period_s=.05, faults=faults)
    return [{'trial_id': row['trial_id'], 'outcome': row['status'], 'evidence': row['wire_evidence']}
            for row in simulation['trial_results']]


def test_repeated_routes_are_separate_and_synthetic_speed_is_not_ranked():
    plan = repeated_plan()
    result = summarize_campaign(plan, observations(plan))
    assert len(result['groups']) == 4
    assert all(g['eligible_count'] == 3 for g in result['groups'])
    assert all(g['reported_endpoint_spread_mm'] == 0 for g in result['groups'])
    assert len(result['host_timing_comparisons']) == 2
    assert all(c['relation'] == 'HOST_BOUNDS_OVERLAP_OR_TOUCH' for c in result['host_timing_comparisons'])
    assert result['recommended_settings'] is None
    assert not result['physical_ready']


def test_endpoint_spread_uses_distinct_reported_endpoints():
    plan = repeated_plan()
    rows = observations(plan)
    trial = plan.to_dict()['trials'][2]
    samples = []
    for i in range(21):
        pose = deepcopy(trial['start'])
        pose['x_mm'] = min(i / 10, 1) * 1.04
        samples.append({'model_elapsed_s': i * .05, 'pose': pose})
    rows[2]['evidence'] = analyze_synthetic_trial(plan, trial['trial_id'], samples)
    result = summarize_campaign(plan, rows)
    assert result['groups'][0]['reported_endpoint_spread_mm'] == pytest.approx(.04)


def test_failed_and_missing_trials_are_preserved_not_averaged_as_zero():
    plan = repeated_plan()
    result = summarize_campaign(plan, observations(plan, {'0-0-out': 'DISCONNECT'}))
    assert len(result['trials']) == 12
    assert result['trials'][0]['outcome'] == 'DISCONNECT'
    assert result['trials'][1]['outcome'] == 'NOT_OBSERVED'
    assert all(g['reported_endpoint_spread_mm'] is None for g in result['groups'])
    assert all(g['status'] == 'INSUFFICIENT_REPETITIONS' for g in result['groups'])


def test_cached_analysis_cannot_override_original_and_mutation_is_rejected():
    plan = repeated_plan()
    rows = observations(plan)
    rows[0]['evidence']['analysis'] = {'status': 'fabricated'}
    assert summarize_campaign(plan, rows)['trials'][0]['analysis']['status'] == 'OBSERVED_SETTLING'
    rows[0]['evidence']['raw']['sha256'] = 'f' * 64
    with pytest.raises(ValueError, match='digest'):
        summarize_campaign(plan, rows)


def test_physical_duplicate_bytes_do_not_count_as_independent_repetitions():
    plan = repeated_plan()
    rows = observations(plan)
    for row in rows:
        row['evidence']['basis'] = 'RETAINED_PHYSICAL_CAPTURE'
        row['outcome'] = 'OBSERVATION_COMPLETED'
    result = summarize_campaign(plan, rows)
    assert 'REUSED_PHYSICAL_CAPTURE_NOT_INDEPENDENT' in result['trials'][2]['exclusions']
    assert result['recommended_settings'] is None


def test_observation_context_cannot_silently_ignore_extra_or_duplicate_trials():
    plan = repeated_plan()
    rows = observations(plan)
    with pytest.raises(ValueError, match='duplicate'):
        summarize_campaign(plan, rows + [rows[0]])
    rows[0]['trial_id'] = 'wrong'
    with pytest.raises(ValueError, match='Unknown'):
        summarize_campaign(plan, rows)
    with pytest.raises(ValueError, match='threshold'):
        summarize_campaign(plan, [], minimum_repetitions=True)


def test_disjoint_host_bounds_are_descriptive_not_physical_speed_ranking():
    plan = repeated_plan()
    rows = observations(plan)
    slower = simulate_campaign(plan, travel_s=.7, sample_period_s=.05)
    for index in range(6, 12):
        rows[index]['evidence'] = slower['trial_results'][index]['wire_evidence']
    result = summarize_campaign(plan, rows)
    assert all(c['relation'] == 'FIRST_HAS_EARLIER_HOST_SETTLING_BOUNDS' for c in result['host_timing_comparisons'])
    assert all(c['physical_speed_ranking'] is None for c in result['host_timing_comparisons'])
    assert result['recommended_settings'] is None
    insufficient = summarize_campaign(plan, rows, minimum_repetitions=4)
    assert all(c['relation'] == 'INSUFFICIENT_REPETITIONS' for c in insufficient['host_timing_comparisons'])


def test_endpoint_evidence_is_not_reinterpreted_as_continuous_comparison():
    plan = repeated_plan()
    rows = observations(plan)
    rows[0]['evidence']['observation_contract'] = 'SUPERVISED_ENDPOINT_ONLY'
    with pytest.raises(ValueError, match='Endpoint-only'):
        summarize_campaign(plan, rows)
