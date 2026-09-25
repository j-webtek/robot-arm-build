"""Public wizard endpoint mode, with incapable coordinator and fixture records."""
import pytest

from rocell.application import wizard_absolute_wrist_coordinator as coordinator
from rocell.application.first_motion_contract import canonical
from rocell.motion.absolute_wrist_diagnostic import AbsoluteWristDiagnosticDraft
from rocell.safety.absolute_wrist_review_authority import AbsoluteWristIntent
from rocell.safety.observational_review_authority import CHECKS
from test_arrival_wizard_service import make_service, _run, _ticket
from test_endpoint_current_context import fixture as endpoint_fixture
from test_absolute_wrist_review_authority import intent


def configure(service, monkeypatch):
    _, _, _, binding = endpoint_fixture()
    body = intent()
    body['session_id'] = service.session_id
    draft = AbsoluteWristDiagnosticDraft(canonical(body['draft']))
    monkeypatch.setattr(service, '_powered_setup_context', lambda: {'synthetic': True})
    receipt = service.configure_absolute_wrist_movement(controller_binding=binding,
        protocol_original=b'{"synthetic":"not physical qualification"}', draft=draft)
    body['attempt_id'] = receipt['attempt_id']
    return draft, AbsoluteWristIntent(canonical(body))


def test_host_staging_shows_absolute_preview_and_no_relative_observation_option(make_service, monkeypatch):
    service, runner, _ = make_service(mode='physical')
    draft, _ = configure(service, monkeypatch)
    view = service.view()
    action = next(a for a in view['actions'] if a['action_id'] == 'run_observational_movement')
    assert action['enabled'] and action['label'] == 'Run one absolute wrist endpoint test'
    assert action['observational_preview']['absolute_target_degrees'] == 0
    assert action['observational_preview']['reviewed_draft'] == draft.to_dict()
    assert 'delta_degrees' not in action['observational_preview']
    assert not runner.calls and service._observational_request is None
    with pytest.raises(Exception): configure(service, monkeypatch)


@pytest.mark.parametrize('endpoint,stage', [('REPORTED_SETTLED', 'RETAINED'),
    ('TARGET_MISSED', 'RETAINED'), (None, 'RETENTION_FAILED')])
def test_public_absolute_run_once_and_truthful_endpoint_status(make_service, monkeypatch, endpoint, stage):
    service, runner, _ = make_service(mode='physical')
    draft, request = configure(service, monkeypatch)
    calls = []
    def confirm(*args, **kwargs):
        assert kwargs['draft'] == draft and 'direction' not in kwargs and 'policy' not in kwargs
        assert kwargs['checks'] == dict.fromkeys(CHECKS, True)
        calls.append('confirm')
        return request, b'synthetic signed record'
    outcome = coordinator.AbsoluteWristRunOutcome(stage, None, None,
        dict(status='RESULT_RETAINED', endpoint_status=endpoint,
             endpoint_reported_settled=endpoint == 'REPORTED_SETTLED') if endpoint else None, None)
    def run(*args, **kwargs):
        kwargs['check_current']()
        calls.append('run')
        return outcome
    monkeypatch.setattr(coordinator, 'confirm_absolute_wrist_run', confirm)
    monkeypatch.setattr(coordinator, 'run_reviewed_absolute_wrist', run)
    values = dict(operator_id='Fixture operator', **dict.fromkeys(CHECKS, True))
    operation = _run(service, 'run_observational_movement', values)
    assert operation['status'] == ('SUCCEEDED' if endpoint == 'REPORTED_SETTLED' else 'FAILED'), operation
    assert operation['result']['motion_mode'] == 'ABSOLUTE_WRIST'
    assert operation['result']['replay_allowed'] is False
    assert calls == ['confirm', 'run'] and not runner.calls
    assert service._observational_outcome is outcome
    with pytest.raises(Exception): _ticket(service, 'run_observational_movement', values)
    # Relative-only operator-assessment code must not consume absolute records.
    record = next(a for a in service.view()['actions'] if a['action_id'] == 'record_observational_movement')
    assert not record['enabled']


def test_changed_setup_blocks_absolute_confirmation(make_service, monkeypatch):
    service, runner, _ = make_service(mode='physical')
    configure(service, monkeypatch)
    monkeypatch.setattr(service, '_powered_setup_context', lambda: {'synthetic': 'changed'})
    with pytest.raises(Exception):
        _ticket(service, 'run_observational_movement', dict(operator_id='Fixture', **dict.fromkeys(CHECKS, True)))
    assert service._observational_confirmation is None and not runner.calls


@pytest.mark.parametrize('fault', [None, 'changed_capture', 'wrong_unit'])
def test_public_setup_selects_only_revalidated_capture_draft(make_service, monkeypatch, fault):
    import hashlib
    from rocell.application import absolute_wrist_telemetry_source as sources
    service, runner, _ = make_service(mode='physical')
    _, _, _, binding = endpoint_fixture()
    monkeypatch.setattr(service, '_powered_setup_context', lambda: {'synthetic': True})
    receipt = service.retain_reviewed_observational_sources(controller_binding=binding,
        protocol_original=b'{"synthetic":"not hardware review"}', label='Synthetic source')
    draft = AbsoluteWristDiagnosticDraft(canonical(intent()['draft']))
    identity = hashlib.sha256(canonical(service._native_arm_report)).hexdigest()
    # Fixture host-owned source association. The production source reader has
    # separate full journal/byte reconstruction tests; no native APIs here.
    service._observational_sources[receipt['source_id']]['onboarding'] = dict(
        original_sha256=dict(native_identity='f'*64 if fault == 'wrong_unit' else identity))
    choices = dict(native_identity_sha256=identity,
        choices=[dict(draft=draft.to_dict(), draft_sha256=draft.sha256)])
    service._absolute_wrist_capture_choices = choices
    def revalidate(root, outcome, **kwargs):
        assert kwargs['session_id'] == service.session_id
        assert kwargs['source_sha256'] == service.source_sha256
        assert kwargs['native_identity_sha256'] == identity
        return dict(choices, changed=True) if fault == 'changed_capture' else choices
    monkeypatch.setattr(sources, 'choices_from_retained_telemetry', revalidate)
    action = next(a for a in service.view()['actions'] if a['action_id'] == 'setup_observational_movement')
    field = next(f for f in action['fields'] if f['name'] == 'absolute_draft')
    assert [o['value'] for o in field['options']] == ['relative', draft.sha256]
    result = _run(service, 'setup_observational_movement', dict(source_id=receipt['source_id'],
        direction='-1', degrees='1', absolute_draft=draft.sha256))
    assert result['status'] == ('SUCCEEDED' if fault is None else 'FAILED'), result
    if fault is None:
        assert service._observational_configuration['absolute_draft'] == draft
        assert service._observational_configuration['direction'] == draft.to_dict()['direction']
    else:
        assert service._observational_configuration is None
    assert not runner.calls
