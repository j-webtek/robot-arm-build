"""Wizard lifecycle with an incapable coordinator double, never native I/O."""
import pytest
from rocell.application.first_motion_draft import FirstMotionDraft
from rocell.application.wizard_first_motion_coordinator import FirstMotionRunOutcome
from rocell.safety.first_motion_review_authority import OPERATOR_CHECKS
from test_first_motion_contract import request
from test_arrival_wizard_service import make_service, _run, _ticket


@pytest.mark.parametrize('stage', ['RETAINED', 'RETENTION_FAILED'])
def test_run_retains_owned_outcome_and_consumes_attachment(make_service, monkeypatch, stage):
    import rocell.application.wizard_first_motion_coordinator as coordinator
    service, runner, _ = make_service(mode='physical')
    draft = FirstMotionDraft.from_request(request())
    # Host attachment itself is exercised separately with actual receipts.
    service._first_motion_attachment = dict(draft=draft, reference_originals={},
        review_selections=(), measurement_operation_id='operation-'+'a'*32)
    monkeypatch.setattr(service, '_powered_setup_context', lambda: {'synthetic':True})
    calls = []
    owned = object()
    outcome = FirstMotionRunOutcome(stage, owned, None,
        {'status':'RESULT_RETAINED'} if stage == 'RETAINED' else None, None)
    def run(workspace, selected, values, **kwargs):
        kwargs['check_current']()
        assert selected is draft
        assert type(kwargs['accepted_ns']) is int
        assert kwargs['attempt_id'] == service._first_motion_attempt_id
        assert set(values) == OPERATOR_CHECKS | {'operator_id','selection_sha256'}
        calls.append(kwargs)
        return outcome
    monkeypatch.setattr(coordinator, 'run_confirmed_first_motion', run)
    values = dict.fromkeys(OPERATOR_CHECKS, True)
    values.update(operator_id='synthetic', selection_sha256=draft.selection_sha256)
    operation = _run(service, 'run_first_motion', values)
    assert operation['status'] == ('SUCCEEDED' if stage == 'RETAINED' else 'FAILED')
    assert service._first_motion_outcome is outcome
    assert service._first_motion_outcome.owned is owned
    assert len(calls) == 1 and not runner.calls
    with pytest.raises(Exception): _ticket(service, 'run_first_motion', values)


def test_unattached_run_is_blocked(make_service):
    service, runner, _ = make_service(mode='physical')
    action = next(a for a in service.view()['actions'] if a['action_id']=='run_first_motion')
    assert not action['enabled']
    assert not runner.calls


@pytest.mark.parametrize('change', ['setup', 'selection', 'state'])
def test_changed_preview_cannot_execute(make_service, monkeypatch, change):
    import rocell.application.wizard_first_motion_coordinator as coordinator
    from rocell.application.first_motion_contract import FirstMotionRequest, canonical
    service, runner, _ = make_service(mode='physical')
    draft = FirstMotionDraft.from_request(request())
    service._first_motion_attachment = dict(draft=draft, reference_originals={},
        review_selections=(), measurement_operation_id='operation-'+'a'*32)
    context = {'synthetic': True}
    monkeypatch.setattr(service, '_powered_setup_context', lambda: dict(context))
    monkeypatch.setattr(coordinator, 'run_confirmed_first_motion',
                        lambda *a, **k: pytest.fail('Stale preview dispatched'))
    values = dict.fromkeys(OPERATOR_CHECKS, True)
    values.update(operator_id='synthetic', selection_sha256=draft.selection_sha256)
    ticket = _ticket(service, 'run_first_motion', values)
    if change == 'setup': context['synthetic'] = False
    elif change == 'selection':
        data = request().to_dict()
        data['distal_radius_mm'] = 190
        service._first_motion_attachment['draft'] = FirstMotionDraft.from_request(FirstMotionRequest(canonical(data)))
    else:
        service._changed(state=True)
    with pytest.raises(Exception): service.execute_action(ticket['ticket_id'])
    assert service._first_motion_attempt_id is None
    assert not runner.calls


def test_repeated_operation_checks_do_not_rescan_source(make_service, monkeypatch):
    import rocell.application.wizard_first_motion_coordinator as coordinator
    service, runner, _ = make_service(mode='physical')
    draft = FirstMotionDraft.from_request(request())
    service._first_motion_attachment = dict(draft=draft, reference_originals={},
        review_selections=(), measurement_operation_id='operation-'+'a'*32)
    monkeypatch.setattr(service, '_powered_setup_context', lambda: {'synthetic':True})
    original_check = service._recheck_source
    scans = []
    def counted(action):
        scans.append(action)
        return original_check(action)
    monkeypatch.setattr(service, '_recheck_source', counted)
    def run(*args, **kwargs):
        before = len(scans)
        for _ in range(20): kwargs['check_current']()
        assert len(scans) == before
        service._source_changed = True
        with pytest.raises(Exception): kwargs['check_current']()
        return FirstMotionRunOutcome('PREPARATION_FAILED', None, None, None, 'SyntheticSourceChange')
    monkeypatch.setattr(coordinator, 'run_confirmed_first_motion', run)
    values = dict.fromkeys(OPERATOR_CHECKS, True)
    values.update(operator_id='synthetic', selection_sha256=draft.selection_sha256)
    operation = _run(service, 'run_first_motion', values)
    assert operation['status'] == 'FAILED'
    assert scans and not runner.calls
