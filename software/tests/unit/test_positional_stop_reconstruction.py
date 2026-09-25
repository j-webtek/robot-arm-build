import pytest
from rocell.application.first_motion_contract import canonical
from rocell.application.positional_stop_reconstruction import reconstruct_stop_measurement, assess_reconstructed_stop_observations
from test_positional_stop_assessment import fixture


def measurement(scope, fault='operator_stop'):
    return dict(schema='rocell.positional_stop_samples.v1', scope=scope, fault=fault,
        source_kind='independent_angular_sensor', clock_domain='fixture_sensor_clock', fault_observed_ns=20_000_000,
        policy=dict(stationary_band_rad=0., minimum_stationary_ns=20_000_000, maximum_sample_gap_ns=10_000_000),
        samples=[dict(t_ns=(i+1)*10_000_000, angle_rad=angle) for i, angle in enumerate([-.01, 0., .005, .005, .005])],
        terminal_state_observed='Fixture observation, not physical evidence', independent_of_host_usb=True)


def test_full_originals_reconstruct_numbers_but_not_physical_authenticity():
    request, record = fixture()
    originals = {}
    for index, trial in enumerate(record['trials']):
        raw = canonical(measurement(record['scope'], trial['fault']))
        reconstructed = reconstruct_stop_measurement(request, raw)
        assert reconstructed['motion_ceased_ns'] == 30_000_000
        assert reconstructed['residual_motion_rad'] == .005
        record['trials'][index] = reconstructed
        originals[reconstructed['measurement_original_sha256']] = raw
    result = assess_reconstructed_stop_observations(request, canonical(record), originals)
    assert result['status'] == 'READY_FOR_ENGINEERING_REVIEW'
    assert result['measurement_originals_verified']
    assert not result['measurement_originals_authenticated'] and not result['physical_stop_verified']
    record['trials'][0]['motion_ceased_ns'] = 20_000_000
    with pytest.raises(ValueError, match='differs'): assess_reconstructed_stop_observations(request, canonical(record), originals)


@pytest.mark.parametrize('fault', ['gap', 'order', 'clock', 'boolean', 'controller', 'scope', 'band'])
def test_invalid_source_or_samples_rejected(fault):
    request, record = fixture()
    value = measurement(record['scope'])
    if fault == 'gap': value['samples'][-1]['t_ns'] += 20_000_000
    if fault == 'order': value['samples'][2]['t_ns'] = value['samples'][1]['t_ns']
    if fault == 'clock': value['fault_observed_ns'] += 1
    if fault == 'boolean': value['samples'][0]['angle_rad'] = True
    if fault == 'controller': value['source_kind'] = 'controller_reported'
    if fault == 'scope': value['scope']['route_sha256'] = 'f'*64
    if fault == 'band': value['policy']['stationary_band_rad'] = -1
    with pytest.raises(ValueError): reconstruct_stop_measurement(request, canonical(value))


def test_later_motion_invalidates_early_plateau_and_retains_no_stop_result():
    request, record = fixture()
    value = measurement(record['scope'])
    value['samples'][-1]['angle_rad'] = .02
    result = reconstruct_stop_measurement(request, canonical(value))
    assert result['motion_ceased_ns'] is None and result['residual_motion_rad'] == .02
