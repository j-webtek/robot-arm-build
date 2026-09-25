import json

import pytest

from rocell.application.first_motion_contract import canonical
from rocell.application.observational_result_review import review_completed_observational_trial
from test_observational_owned_trial import run


def fixture(tmp_path):
    request, result, _ = run(tmp_path)
    selection = (tmp_path/(request.to_dict()['attempt_id']+'-observational-command-selection.json')).read_bytes()
    return request, result, selection


def test_reconstructs_originals_without_inventing_observation(tmp_path):
    request, result, selection = fixture(tmp_path)
    report = review_completed_observational_trial(request, canonical(result), selection,
        expected_basis='SYNTHETIC_WIRE_REHEARSAL')
    assert report['status'] == 'TRIAL_DATA_CONSISTENT_AWAITING_OBSERVATION'
    assert report['analysis']['operator_outcome'] == 'UNKNOWN'
    assert report['owned_process_verified'] is False
    assert report['motion_authorized'] is False


@pytest.mark.parametrize('fault', ['basis', 'request', 'bytes', 'write_time', 'cleanup',
    'raw', 'coverage', 'preview', 'hash', 'claim', 'selection_unit'])
def test_tampered_success_cannot_pass(tmp_path, fault):
    request, result, selection = fixture(tmp_path)
    if fault == 'basis': result['basis'] = 'RETAINED_PHYSICAL_CAPTURE'
    if fault == 'request': result['request_sha256'] = 'a'*64
    if fault == 'bytes': result['write']['confirmed_write_bytes'] -= 1
    if fault == 'write_time': result['write']['write_started_ns'] += 1_000_000_000
    if fault == 'cleanup': result['cleanup']['pending_io_count'] = 1
    if fault == 'raw': result['post']['raw']['sha256'] = 'b'*64
    if fault == 'coverage': result['post']['coverage']['retained_bytes'] = 0
    if fault == 'preview': result['selection']['preview']['candidate_command']['spd'] = 0
    if fault == 'hash': result['selection']['selection_sha256'] = 'c'*64
    if fault == 'claim': result['physical_movement_verified'] = True
    if fault == 'selection_unit':
        changed = json.loads(selection)
        changed['usb_identity']['serial_number'] = 'B'*32
        selection = canonical(changed)
    with pytest.raises(ValueError):
        review_completed_observational_trial(request, canonical(result), selection,
            expected_basis='SYNTHETIC_WIRE_REHEARSAL')


def test_uncertain_submission_is_retained_but_not_promoted(tmp_path):
    request, result, _ = run(tmp_path, 'short_write')
    selection = (tmp_path/(request.to_dict()['attempt_id']+'-observational-command-selection.json')).read_bytes()
    with pytest.raises(ValueError):
        review_completed_observational_trial(request, canonical(result), selection,
            expected_basis='SYNTHETIC_WIRE_REHEARSAL')
    assert result['post']['raw']['bytes'] > 0
