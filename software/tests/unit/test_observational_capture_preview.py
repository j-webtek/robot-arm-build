from types import SimpleNamespace

import pytest

from rocell.application.observational_capture_preview import summarize_capture
from rocell.application.wizard_powered_feedback_native_coordinator import PoweredFeedbackOutcome
from rocell.arm.telemetry_stream import TelemetryStream, compact_capture
from test_first_motion_analysis import wire


def observation(corrupt_at=None):
    raw, windows = wire([.02] * 100, 2_000_000_000, corrupt_at=corrupt_at)
    parser = TelemetryStream()
    parser.feed(raw)
    return dict(schema='rocell.powered_telemetry_observation.v2', status='CAPTURED_CLOSED',
        errors=[], capture=compact_capture(parser.finish()), read_windows=windows,
        started_monotonic_ns=2_000_000_000, observation_finished_monotonic_ns=7_000_000_000,
        lifecycle=dict(cleanup_confirmed=True, confirmed_write_bytes=0))


def publication(obs, status='SUCCEEDED'):
    process = SimpleNamespace(parsed_result=dict(child_result=dict(observation=obs)),
        status=status, process_created=True, initial_thread_resumed=True, tree_exit_confirmed=True)
    return PoweredFeedbackOutcome(process, 'a' * 64, None,
        action_id='capture_powered_arm_telemetry').publication()


def test_actual_capture_publication_includes_historical_preview():
    result = publication(observation())
    assert result['status'] == 'SUCCEEDED'
    report = result['steps'][0]['report']['observational_wrist_preview']
    assert report['status'] == 'HISTORICAL_PREVIEW_AVAILABLE'
    assert report['full_capture_frame_count'] == 100
    assert report['selected_frame_count'] == 20
    assert report['historical_only'] is True
    assert report['motion_authorized'] is False
    assert report['preview']['precision_measurements_required'] is False


def test_invalid_early_frame_is_not_hidden_by_clean_tail():
    obs = observation(corrupt_at=3)
    report = summarize_capture(obs)
    assert report['status'] == 'HELD'
    assert 'INVALID_JOINT_RECORD' in report['hold_reason']
    # The primary capture remains exportable even when movement planning holds.
    result = publication(obs)
    assert result['status'] == 'SUCCEEDED'
    assert result['steps'][0]['report']['observational_wrist_preview']['status'] == 'HELD'


@pytest.mark.parametrize('fault', ['hash', 'length', 'base64', 'failed', 'missing'])
def test_malformed_capture_is_a_diagnostic_hold(fault):
    obs = observation()
    if fault == 'hash': obs['capture']['raw']['sha256'] = 'b' * 64
    if fault == 'length': obs['capture']['raw']['bytes'] += 1
    if fault == 'base64': obs['capture']['raw']['base64'] = '!!'
    if fault == 'failed': obs['status'] = 'FAILED'
    if fault == 'missing': del obs['read_windows']
    assert summarize_capture(obs)['status'] == 'HELD'


def test_failed_owned_process_never_produces_movement_preview():
    result = publication(observation(), status='FAILED')
    assert result['status'] == 'FAILED'
    assert result['steps'][0]['report']['observational_wrist_preview'] is None


def test_startup_latency_requires_explicit_v3_evidence_not_relabeling_v2():
    obs = observation()
    obs['started_monotonic_ns'] -= 156_000_000
    assert summarize_capture(obs)['status'] == 'HELD'
    obs['schema'] = 'rocell.powered_telemetry_observation.v3'
    obs['acquisition_started_monotonic_ns'] = 2_000_000_000
    report = summarize_capture(obs)
    assert report['status'] == 'HISTORICAL_PREVIEW_AVAILABLE'
    assert report['startup_duration_ns'] == 156_000_000
    assert report['startup_timing_separated'] is True
    assert report['motion_authorized'] is False


@pytest.mark.parametrize('fault', ['missing', 'future', 'pre-read', 'bool', 'initial-gap', 'interior-gap'])
def test_v3_cannot_hide_missing_acquisition_evidence_or_real_gaps(fault):
    obs = observation()
    obs['schema'] = 'rocell.powered_telemetry_observation.v3'
    obs['acquisition_started_monotonic_ns'] = 2_000_000_000
    if fault == 'missing': del obs['acquisition_started_monotonic_ns']
    elif fault == 'future': obs['acquisition_started_monotonic_ns'] = 8_000_000_000
    elif fault == 'pre-read': obs['acquisition_started_monotonic_ns'] += 100_000_000
    elif fault == 'bool': obs['acquisition_started_monotonic_ns'] = True
    elif fault == 'initial-gap':
        obs['started_monotonic_ns'] -= 200_000_000
        obs['acquisition_started_monotonic_ns'] -= 200_000_000
    else:
        for row in obs['read_windows'][50:]:
            row[2] += 150_000_000
            row[3] += 150_000_000
        obs['observation_finished_monotonic_ns'] += 150_000_000
    assert summarize_capture(obs)['status'] == 'HELD'
