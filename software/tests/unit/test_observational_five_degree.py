"""Five-degree policy integration; synthetic feedback never certifies hardware."""
import math

import pytest

from rocell.application.first_motion_contract import canonical
from rocell.application.observational_result_review import review_completed_observational_trial
from rocell.motion.observational_wrist_plan import (
    FIVE_DEGREE_POLICY, ONE_DEGREE_POLICY, preview_observational_wrist,
)
from rocell.safety.observational_review_authority import ObservationalReviewAuthority
from test_observational_wrist_plan import capture
from test_observational_review_authority import intent, review
from test_observational_owned_trial import run
from test_arrival_wizard_service import make_service


@pytest.mark.parametrize('direction', [-1, 1])
def test_five_degree_exact_target_and_unchanged_speed(direction):
    result = preview_observational_wrist(samples=capture(), now_ns=1_300_000_000,
        direction=direction, policy=FIVE_DEGREE_POLICY)
    assert result['candidate_command'] == dict(T=101, joint=4,
        rad=.02 + direction*math.radians(5), spd=20, acc=1)
    assert result['motion_authorized'] is False


@pytest.mark.parametrize('direction', [-1, 1])
def test_five_degree_keeps_ten_degree_envelope(direction):
    samples = capture()
    for sample in samples:
        sample['joints_rad']['t'] = direction*math.radians(6)
    with pytest.raises(ValueError, match='envelope'):
        preview_observational_wrist(samples=samples, now_ns=1_300_000_000,
            direction=direction, policy=FIVE_DEGREE_POLICY)


def test_one_degree_approval_cannot_be_reinterpreted_as_five():
    authority = ObservationalReviewAuthority(b'K'*32)
    body = intent()
    signed = authority.seal(body, review(), now_ns=1_000_000_002)
    body['policy'] = FIVE_DEGREE_POLICY
    with pytest.raises(ValueError):
        authority.verify(signed, expected_intent=body,
            current_usb_identity=body['usb_identity'], current_references=body['references'],
            now_ns=1_000_000_003)


def test_five_degree_owned_sequence_and_result_reconstruction(tmp_path, monkeypatch):
    import test_observational_current_context as context
    def five_intent():
        body = intent()
        body['policy'] = FIVE_DEGREE_POLICY
        return body
    monkeypatch.setattr(context, 'intent', five_intent)
    request, result, calls = run(tmp_path)
    assert calls['write'] == 1 and calls['close'] == 1
    assert result['status'] == 'AWAITING_OPERATOR_OBSERVATION'
    selection = (tmp_path/(request.to_dict()['attempt_id']+'-observational-command-selection.json')).read_bytes()
    report = review_completed_observational_trial(request, canonical(result), selection,
        expected_basis='SYNTHETIC_WIRE_REHEARSAL')
    assert report['analysis']['preview']['requested_delta_rad'] == -math.radians(5)
    assert report['motion_authorized'] is False


def test_public_five_degree_setup_display_and_policy(make_service, monkeypatch):
    from test_endpoint_current_context import fixture
    from test_arrival_wizard_service import _run
    service, runner, _ = make_service(mode='physical')
    _, _, _, binding = fixture()
    monkeypatch.setattr(service, '_powered_setup_context', lambda: {'synthetic': True})
    receipt = service.retain_reviewed_observational_sources(controller_binding=binding,
        protocol_original=b'{"synthetic":true}', label='Synthetic reviewed arm')
    operation = _run(service, 'setup_observational_movement',
        dict(source_id=receipt['source_id'], direction='-1', degrees='5'))
    assert operation['status'] == 'SUCCEEDED', operation
    assert service._observational_configuration['policy'] == FIVE_DEGREE_POLICY
    action = next(a for a in service.view()['actions'] if a['action_id'] == 'run_observational_movement')
    assert action['observational_preview']['delta_degrees'] == -5
    assert not runner.calls
