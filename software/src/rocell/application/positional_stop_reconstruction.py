"""Recompute angular stop observations from retained independent sample records.

Recorded sensor/video data is not automatically authenticated or calibrated.
Stationarity is a sampled angular criterion, not proof of zero motion, safe
torque, Cartesian containment, or a safe terminal state between samples.
"""
import hashlib
import math

from .first_motion_contract import canonical
from .wizard_diagnostic_coordinator import decode_diagnostic_json
from .positional_stop_assessment import assess_stop_observations, expected_scope, FAULTS


def reconstruct_stop_measurement(request, raw):
    if type(raw) is not bytes:
        raise ValueError('Immutable measurement original required')
    value = decode_diagnostic_json(raw, maximum=2_097_152)
    fields = {'schema', 'scope', 'fault', 'source_kind', 'clock_domain', 'fault_observed_ns',
        'policy', 'samples', 'terminal_state_observed', 'independent_of_host_usb'}
    if (type(value) is not dict or set(value) != fields or canonical(value) != raw
            or value['schema'] != 'rocell.positional_stop_samples.v1'
            or value['scope'] != expected_scope(request) or value['fault'] not in FAULTS
            or value['source_kind'] not in ('independent_angular_sensor', 'independent_video_tracking')
            or type(value['clock_domain']) is not str or not 1 <= len(value['clock_domain']) <= 128
            or type(value['independent_of_host_usb']) is not bool
            or type(value['terminal_state_observed']) is not str
            or not 1 <= len(value['terminal_state_observed'].strip()) <= 2048):
        raise ValueError('Exact scoped independent sample record required')
    policy = value['policy']
    if type(policy) is not dict or set(policy) != {'stationary_band_rad', 'minimum_stationary_ns', 'maximum_sample_gap_ns'}:
        raise ValueError('Explicit angular stationarity policy required')
    band = policy['stationary_band_rad']
    if (type(band) not in (int, float) or not math.isfinite(band) or band < 0
            or any(type(policy[k]) is not int or not 0 < policy[k] < 2**63
                for k in ('minimum_stationary_ns', 'maximum_sample_gap_ns'))):
        raise ValueError('Finite positive timing bounds and nonnegative angular band required')
    samples = value['samples']
    if type(samples) is not list or not 3 <= len(samples) <= 10000:
        raise ValueError('Bounded ordered angular samples required')
    previous = 0
    for row in samples:
        if (type(row) is not dict or set(row) != {'t_ns', 'angle_rad'}
                or type(row['t_ns']) is not int or not previous < row['t_ns'] < 2**63
                or (previous and row['t_ns']-previous > policy['maximum_sample_gap_ns'])
                or type(row['angle_rad']) not in (int, float)
                or not math.isfinite(row['angle_rad']) or abs(row['angle_rad']) > 100):
            raise ValueError('Invalid, unordered or gapped angular samples')
        previous = row['t_ns']
    fault = value['fault_observed_ns']
    if type(fault) is not int:
        raise ValueError('Fault time must use the measurement clock')
    indices = [i for i, row in enumerate(samples) if row['t_ns'] == fault]
    if len(indices) != 1 or indices[0] == 0:
        raise ValueError('Exact fault-time sample and pre-fault evidence required')
    start = indices[0]
    # One backwards pass computes each suffix's range, avoiding quadratic
    # rescans and rejecting a false early plateau followed by later motion.
    low = high = samples[-1]['angle_rad']
    ceased = None
    for index in range(len(samples)-1, start-1, -1):
        row = samples[index]
        low, high = min(low, row['angle_rad']), max(high, row['angle_rad'])
        if (high-low <= band and samples[-1]['t_ns']-row['t_ns'] >= policy['minimum_stationary_ns']):
            ceased = row['t_ns']
    residual = max(abs(row['angle_rad']-samples[start]['angle_rad']) for row in samples[start:])
    return dict(fault=value['fault'], fault_observed_ns=fault, motion_ceased_ns=ceased,
        residual_motion_rad=residual, measurement_original_sha256=hashlib.sha256(raw).hexdigest(),
        terminal_state_observed=value['terminal_state_observed'],
        independent_of_host_usb=value['independent_of_host_usb'])


def assess_reconstructed_stop_observations(request, observation_raw, measurement_originals):
    """Compare every claimed trial with its original; never promote release."""
    assessment = assess_stop_observations(request, observation_raw)
    value = decode_diagnostic_json(observation_raw, maximum=131072)
    if type(measurement_originals) is not dict or len(measurement_originals) > 32:
        raise ValueError('Bounded measurement originals keyed by digest required')
    used = set()
    for trial in value['trials']:
        digest = trial['measurement_original_sha256']
        if digest not in measurement_originals or digest in used:
            raise ValueError('Missing or reused stop measurement original')
        original = measurement_originals[digest]
        reconstructed = reconstruct_stop_measurement(request, original)
        if canonical(reconstructed) != canonical(trial):
            raise ValueError('Stop observation differs from original samples')
        used.add(digest)
    if used != set(measurement_originals):
        raise ValueError('Unassociated stop measurement originals')
    return dict(assessment, measurement_originals_verified=True,
        measurement_originals_authenticated=False, angular_samples_only=True)
