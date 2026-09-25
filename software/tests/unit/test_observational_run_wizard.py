"""Public run lifecycle with an incapable coordinator, not native hardware."""
import pytest
from rocell.application import wizard_observational_coordinator as coordinator
from rocell.application.first_motion_contract import canonical
from rocell.safety.observational_review_authority import CHECKS, ObservationalIntent
from test_arrival_wizard_service import make_service, _run, _ticket
from test_observational_review_authority import intent


@pytest.mark.parametrize('stage', ['RETAINED', 'RETENTION_FAILED'])
def test_public_run_once_retains_outcome(make_service, monkeypatch, stage):
    from types import SimpleNamespace
    service, runner, _ = make_service(mode='physical')
    body = intent()
    body['session_id'] = service.session_id
    staged = SimpleNamespace(attempt_id=body['attempt_id'])
    context = {'synthetic':True}
    service._observational_configuration = dict(staged=staged, context=context,
        direction=-1, degrees=1, policy=body['policy'], usb_identity=body['usb_identity'])
    monkeypatch.setattr(service, '_powered_setup_context', lambda: dict(context))
    calls = []
    request = ObservationalIntent(canonical(body))

    def confirm(*args, **kwargs):
        assert kwargs['checks'] == dict.fromkeys(CHECKS, True)
        assert kwargs['accepted_ns'] <= kwargs['now_ns']
        calls.append('confirm')
        return request, b'SYNTHETIC_SIGNED_RECORD'

    outcome = coordinator.ObservationalRunOutcome(stage, object(), None,
        dict(status='RESULT_RETAINED') if stage == 'RETAINED' else None, None)

    def run(*args, **kwargs):
        kwargs['check_current']()
        # The in-flight UI must not claim zero device access for a live action.
        active = [o for o in service._operations.values()
                  if o['action_id'] == 'run_observational_movement']
        assert len(active) == 1 and active[0]['status'] == 'RUNNING'
        assert 'may open the arm and move it' in active[0]['message']
        assert 'not a physical stop' in active[0]['message']
        assert 'No hardware endpoint is opened' not in active[0]['message']
        calls.append('run')
        return outcome

    monkeypatch.setattr(coordinator, 'confirm_observational_run', confirm)
    monkeypatch.setattr(coordinator, 'run_reviewed_observational', run)
    values = dict(operator_id='Jack', **dict.fromkeys(CHECKS, True))
    operation = _run(service, 'run_observational_movement', values)
    assert operation['status'] == ('SUCCEEDED' if stage == 'RETAINED' else 'FAILED'), operation
    assert service._observational_outcome is outcome
    assert service._observational_request is request
    assert calls == ['confirm','run'] and not runner.calls
    with pytest.raises(Exception): _ticket(service, 'run_observational_movement', values)


def test_unconfigured_run_held(make_service):
    service, runner, _ = make_service(mode='physical')
    action = next(a for a in service.view()['actions'] if a['action_id'] == 'run_observational_movement')
    assert not action['enabled'] and not runner.calls


@pytest.mark.parametrize('setup_current', [False, True])
def test_setup_preview_requires_current_powered_context(make_service, monkeypatch, setup_current):
    """Show missing/expired setup before accepting a prepare ticket, without IO."""
    from rocell.application.arrival_wizard_service import WizardError
    from test_endpoint_current_context import fixture
    service, runner, _ = make_service(mode='physical')
    _, _, _, binding = fixture()
    receipt = service.retain_reviewed_observational_sources(
        controller_binding=binding,
        protocol_original=b'{"synthetic":"reviewed input fixture only"}',
        label='Synthetic reviewed arm')

    def context():
        if not setup_current:
            raise WizardError('POWERED_SETUP_REQUIRED', 'Record fresh powered startup first.')
        return {'synthetic': True}

    monkeypatch.setattr(service, '_powered_setup_context', context)
    view = next(a for a in service.view()['actions']
                if a['action_id'] == 'setup_observational_movement')
    assert view['enabled'] is setup_current
    if not setup_current:
        assert 'Record fresh powered startup first.' in view['blocked_reasons']
        with pytest.raises(WizardError):
            _ticket(service, 'setup_observational_movement',
                    dict(source_id=receipt['source_id'], direction='-1'))
    assert service._observational_configuration is None
    assert service._observational_request is None and not runner.calls


def test_export_recovers_raw_bytes_after_report_publication_failure(make_service):
    import base64
    import json
    from pathlib import Path
    from rocell.providers.windows.owned_worker_process import OwnedWorkerResult
    service, runner, _ = make_service(mode='physical')
    receipt = OwnedWorkerResult('FAILED', 'SYNTHETIC_FAILURE', (), 'a'*64,
        'operation-'+'b'*32, False, False, False, None, 1, 0, 0, 0,
        b'synthetic raw stdout', b'synthetic raw stderr')
    service._observational_outcome = coordinator.ObservationalRunOutcome(
        'RETENTION_FAILED', receipt, None, None, 'SyntheticExportFailure')
    operation = _run(service, 'export_logs')
    assert operation['status'] == 'SUCCEEDED', operation
    folder = Path(operation['result']['receipt']['path'])
    payload = json.loads((folder/'attachment-observational-native-logs.json').read_bytes())
    for name in ('stdout', 'stderr'):
        restored = b''.join(base64.b64decode(chunk, validate=True) for chunk in payload[name+'_base64_chunks'])
        assert restored == getattr(receipt, name)
    assert payload['stage'] == 'RETENTION_FAILED' and not runner.calls


def test_trusted_setup_stages_without_measurements_or_device_access(make_service, monkeypatch):
    from test_endpoint_current_context import fixture
    service, runner, _ = make_service(mode='physical')
    _, _, _, binding = fixture()
    monkeypatch.setattr(service, '_powered_setup_context', lambda: {'synthetic':True})
    report = service.configure_observational_movement(controller_binding=binding,
        protocol_original=b'{"synthetic":"protocol fixture, not approval"}')
    assert report['motion_authorized'] is False
    assert service._observational_configuration['staged'].attempt_id == report['attempt_id']
    assert service._observational_request is None
    with pytest.raises(Exception):
        service.configure_observational_movement(controller_binding=binding, protocol_original=b'{}')
    assert not runner.calls


@pytest.mark.parametrize('changed', [False, True])
def test_public_setup_resolves_only_unchanged_host_reviewed_sources(make_service, monkeypatch, changed):
    from test_endpoint_current_context import fixture
    service, runner, _ = make_service(mode='physical')
    _, _, _, binding = fixture()
    monkeypatch.setattr(service, '_powered_setup_context', lambda: {'synthetic':True})
    receipt = service.retain_reviewed_observational_sources(controller_binding=binding,
        protocol_original=b'{"synthetic":"reviewed input fixture only"}', label='Synthetic reviewed arm')
    if changed:
        (service._log.root/(receipt['source_id']+'-controller.json')).write_bytes(b'{}')
    operation = _run(service, 'setup_observational_movement', dict(source_id=receipt['source_id'], direction='-1'))
    assert operation['status'] == ('FAILED' if changed else 'SUCCEEDED'), operation
    assert (service._observational_configuration is not None) is (not changed)
    assert service._observational_request is None and not runner.calls


@pytest.mark.parametrize('fault', [None, 'late', 'unchecked'])
def test_final_click_compiles_actual_staged_refs_without_renewal(tmp_path, monkeypatch, fault):
    from test_observational_worker_preparation import fixture
    workspace, staged, template, _, _, _ = fixture(tmp_path, monkeypatch)
    checks = dict.fromkeys(CHECKS, True)
    if fault == 'unchecked': checks['secured_and_clear'] = False
    def compile_click():
        return coordinator.confirm_observational_run(workspace, staged,
            session_id=template.to_dict()['session_id'], usb_identity=template.to_dict()['usb_identity'],
            direction=-1, operator_id='Jack', checks=checks, accepted_ns=1_000_000_000,
            now_ns=5_000_000_000 if fault == 'late' else 2_000_000_000)
    if fault:
        with pytest.raises(ValueError): compile_click()
    else:
        request, signed = compile_click()
        assert request.to_dict()['issued_ns'] == 1_000_000_000
        assert request.to_dict()['references'] == template.to_dict()['references']
        from rocell.providers.windows.bench_review_key import load_host_observational_review_authority
        assert load_host_observational_review_authority(workspace).verify(signed,
            expected_intent=request.to_dict(), current_usb_identity=request.to_dict()['usb_identity'],
            current_references=request.to_dict()['references'], now_ns=2_000_000_000)
