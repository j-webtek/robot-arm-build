import pytest
from rocell.application import held_elbow_trial_draft as draft


@pytest.fixture
def reference(monkeypatch):
    report = dict(stable_status_observed=True, assessment=dict(
        category='CONTROLLER_REPORTED_HOLD_VERIFIED', boot_id='11'*16,
        endpoint=dict(torque_settled=1, servo_id=14, settled_position=2902)))
    monkeypatch.setattr(draft, 'replay_hold_observation', lambda *a: report)
    monkeypatch.setattr(draft, '_read', lambda *a: ({'prepared_export_id':'fixture'}, '22'*32))
    monkeypatch.setattr(draft, '_prepared', lambda *a: (None, None, None,
        {'joints': [[0,4095]]*3+[[2893,2909]]+[[0,4095]]*3}, None))
    return report


def test_draft_retains_frozen_return_without_live_authority(tmp_path, reference):
    result = draft.draft_held_elbow_trial(tmp_path, 'fixture')
    assert result['illustrative_targets'] == [2908,2902]
    assert result['offsets_from_fresh_anchor'] == [6,0]
    assert result['fresh_held_anchor_required'] and result['verified_export_before_return_required']
    assert not result['progression_authority'] and not result['retry_allowed']
    reverse = draft.draft_held_elbow_trial(tmp_path, 'fixture', offset_counts=-6)
    assert reverse['illustrative_targets'] == [2896,2902]


@pytest.mark.parametrize('offset', [0, 4, -4, True, 1.5, 8, 17, -17])
def test_invalid_or_out_of_envelope_offsets(tmp_path, reference, offset):
    with pytest.raises(ValueError):
        draft.draft_held_elbow_trial(tmp_path, 'fixture', offset_counts=offset)


def test_inconclusive_reference_cannot_form_plan(tmp_path, reference):
    reference['assessment']['category'] = 'INCONCLUSIVE'
    with pytest.raises(ValueError):
        draft.draft_held_elbow_trial(tmp_path, 'fixture')
