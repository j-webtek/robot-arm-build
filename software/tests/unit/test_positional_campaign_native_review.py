import json

import pytest

from rocell.application.first_motion_contract import canonical
from rocell.application.positional_campaign_native_review import review_native_campaign
from rocell.application.positional_campaign_reconstruction import verify_completed_owned_campaign
from rocell.safety.positional_campaign_authority import PositionalCampaignIntent
from test_positional_campaign_native_capture import exercise


def trial(tmp_path, monkeypatch, **kwargs):
    result = exercise(tmp_path, monkeypatch, **kwargs)[-1]
    original = json.loads(next(tmp_path.glob('*-owner.json')).read_bytes())
    return PositionalCampaignIntent(canonical(original['intent'])), result


@pytest.mark.parametrize('missed_leg', [None, 1, 2])
@pytest.mark.parametrize('fragment_size', [None, 23])
def test_reconstruct_native_whole_and_held_campaigns(tmp_path, monkeypatch, missed_leg, fragment_size):
    request, result = trial(tmp_path, monkeypatch, missed_leg=missed_leg, fragment_size=fragment_size)
    review = review_native_campaign(request, result)
    assert review['valid']
    assert review['reconstructed_status'] == result['status']
    assert not review['native_process_verified'] and not review['motion_authorized']
    with pytest.raises(ValueError): verify_completed_owned_campaign(request, result)


@pytest.mark.parametrize('fault', ['raw', 'verdict', 'phase_calls', 'phase_bytes', 'total_bytes',
    'cleanup', 'late_bytes', 'submission_count', 'order', 'identity', 'provenance', 'authority'])
def test_native_result_changes_are_rejected(tmp_path, monkeypatch, fault):
    request, result = trial(tmp_path, monkeypatch)
    lifecycle = result['lifecycle']
    if fault == 'raw': result['legs'][0]['post']['raw']['base64_chunks'][0] = 'e30='
    if fault == 'verdict': result['legs'][0]['verification']['endpoint']['final_error_rad'] = 1
    if fault == 'phase_calls': lifecycle['legs'][0]['read_calls']['post'] += 1
    if fault == 'phase_bytes': lifecycle['legs'][0]['read_bytes']['post'] += 1
    if fault == 'total_bytes': lifecycle['confirmed_write_bytes'] += 1
    if fault == 'cleanup': result['cleanup']['finished_ns'] += 3_000_000_000
    if fault == 'late_bytes': lifecycle['late_cleanup_read_base64'] = 'e30='
    if fault == 'submission_count': result['native_submission_attempts'] = True
    if fault == 'order': result['legs'].reverse()
    if fault == 'identity': lifecycle['connection_id'] = 'another-campaign'
    if fault == 'provenance': result['basis'] = 'SYNTHETIC_WIRE_REHEARSAL'
    if fault == 'authority': result['physical_movement_verified'] = True
    with pytest.raises(ValueError): review_native_campaign(request, result)


@pytest.mark.parametrize('failure', ['setup_error', 'read_error', 'write_error', 'cancel_before_open'])
def test_incomplete_native_campaign_remains_diagnostic(tmp_path, monkeypatch, failure):
    request, result = trial(tmp_path, monkeypatch, failure=failure)
    with pytest.raises(ValueError): review_native_campaign(request, result)
