import pytest
from rocell.application.first_motion_contract import canonical
from rocell.application.positional_stop_assessment import assess_stop_observations, expected_scope, FAULTS, SCHEMA
from rocell.safety.positional_campaign_authority import PositionalCampaignIntent
from test_positional_campaign_authority import body


def fixture():
    request = PositionalCampaignIntent(canonical(body()))
    record = dict(schema=SCHEMA, scope=expected_scope(request), basis='PHYSICAL_OBSERVATIONS',
        installed_behavior_basis='Synthetic test fixture; not a hardware qualification',
        strategy='Fixture strategy', gravity_load_review='Fixture load review',
        safe_terminal_definition='Fixture terminal definition',
        limits=dict(maximum_response_ms=100, maximum_residual_motion_rad=.01),
        trials=[dict(fault=fault, fault_observed_ns=1_000_000_000, motion_ceased_ns=1_050_000_000,
            residual_motion_rad=.005, measurement_original_sha256='a'*64,
            terminal_state_observed='Fixture terminal observation', independent_of_host_usb=True) for fault in FAULTS])
    return request, record


def test_complete_numbers_are_review_ready_not_physical_release():
    request, record = fixture()
    result = assess_stop_observations(request, canonical(record))
    assert result['status'] == 'READY_FOR_ENGINEERING_REVIEW'
    assert all(row['response_ms'] == 50 for row in result['trials'])
    for name in ('measurement_originals_verified', 'reviewer_identity_authenticated',
            'physical_stop_verified', 'motion_authorized', 'unattended_release'):
        assert result[name] is False


@pytest.mark.parametrize('fault', ['missing_trial', 'timing', 'residual', 'late', 'drift',
    'measurement', 'terminal', 'independence', 'gravity'])
def test_incomplete_or_failed_measurements_remain_held(fault):
    request, record = fixture()
    trial = record['trials'][-1]
    if fault == 'missing_trial': record['trials'].pop()
    if fault == 'timing': trial['motion_ceased_ns'] = None
    if fault == 'residual': trial['residual_motion_rad'] = None
    if fault == 'late': trial['motion_ceased_ns'] += 1_000_000_000
    if fault == 'drift': trial['residual_motion_rad'] = .1
    if fault == 'measurement': trial['measurement_original_sha256'] = '0'*64
    if fault == 'terminal': trial['terminal_state_observed'] = ''
    if fault == 'independence': trial['independent_of_host_usb'] = False
    if fault == 'gravity': record['gravity_load_review'] = ''
    assert assess_stop_observations(request, canonical(record))['status'] == 'HELD'


def test_good_repeat_does_not_hide_failed_trial():
    request, record = fixture()
    record['trials'].append(dict(record['trials'][0], motion_ceased_ns=None))
    assert assess_stop_observations(request, canonical(record))['status'] == 'HELD'


@pytest.mark.parametrize('fault', ['unit', 'route', 'basis', 'boolean_limit'])
def test_scope_or_type_mismatch_rejected(fault):
    request, record = fixture()
    if fault == 'unit': record['scope']['usb_identity']['serial_number'] = 'B'*32
    if fault == 'route': record['scope']['route_sha256'] = 'f'*64
    if fault == 'basis': record['basis'] = 'SIMULATION'
    if fault == 'boolean_limit': record['limits']['maximum_response_ms'] = True
    with pytest.raises(ValueError): assess_stop_observations(request, canonical(record))
