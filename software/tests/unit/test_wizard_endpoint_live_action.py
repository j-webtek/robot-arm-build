"""Public endpoint routing with synthetic binding and incapable coordinator."""

import pytest

from rocell.application import wizard_endpoint_coordinator as coordinator
from rocell.application.endpoint_trial_draft import EndpointTrialDraft
from rocell.application.endpoint_reference_reader import ORIGINAL_REFERENCES
from rocell.application.wizard_actions import WizardError
from rocell.safety.bench_review_authority import OPERATOR_CHECKS
from test_endpoint_trial_contract import request
from test_arrival_wizard_service import make_service, _ticket, _run


def attach(service,monkeypatch):
    draft = EndpointTrialDraft.from_request(request())
    binding = coordinator.EndpointWizardBinding(draft,
        tuple((key,b'{"test":true}') for key in sorted(ORIGINAL_REFERENCES)),
        lambda r:{},lambda r:{},lambda r:lambda:None)
    service._endpoint_binding = binding
    monkeypatch.setattr(service,'_powered_setup_context',lambda:{'synthetic':'setup'})
    return {'draft_sha256':draft.draft_sha256,'acknowledge':True,
            'operator_id':'synthetic-operator',**dict.fromkeys(OPERATOR_CHECKS,True)}


def test_no_binding_and_rehearsal_are_held(make_service,monkeypatch):
    physical,runner,_ = make_service(mode='physical')
    with pytest.raises(WizardError): _ticket(physical,'run_endpoint_trial',
        {'draft_sha256':'a'*64,'acknowledge':True})
    rehearsal,_,_ = make_service()
    values = attach(rehearsal,monkeypatch)
    with pytest.raises(WizardError): _ticket(rehearsal,'run_endpoint_trial',values)
    assert not runner.calls


def test_public_parent_path_is_one_use_and_retains_failed_result(make_service,monkeypatch):
    service,runner,_ = make_service(mode='physical')
    values = attach(service,monkeypatch)
    calls = []
    def incapable(workspace,draft,**kwargs):
        kwargs['check_current']()
        calls.append(kwargs)
        return coordinator.EndpointRunOutcome('REVIEW_ISSUANCE_FAILED',None,None,None,'ValueError')
    monkeypatch.setattr(coordinator,'run_endpoint_draft',incapable)
    preview = _ticket(service,'run_endpoint_trial',values)
    assert 'motion command' in ' '.join(preview['effects'])
    result = _run(service,'run_endpoint_trial',values)
    assert result['status']=='FAILED'
    assert 'steps' in result['result'],result
    assert result['result']['steps'][0]['stage']=='REVIEW_ISSUANCE_FAILED'
    assert len(calls)==1 and calls[0]['export_root']==service.export_directory
    req = calls[0]['prepared_request']
    assert req.to_dict()['attempt_id'] == result['operation_id']
    assert set(calls[0]['operator_reader'](req)) == OPERATOR_CHECKS
    assert (service._log.root/(result['operation_id']+'-endpoint-confirmed-request.json')).read_bytes() == req.canonical_bytes
    assert not runner.calls
    with pytest.raises(WizardError): _ticket(service,'run_endpoint_trial',values)


def test_changed_setup_between_preview_and_execute_refused(make_service,monkeypatch):
    service,runner,_ = make_service(mode='physical')
    values = attach(service,monkeypatch)
    preview = _ticket(service,'run_endpoint_trial',values)
    monkeypatch.setattr(service,'_powered_setup_context',lambda:{'synthetic':'changed'})
    with pytest.raises(WizardError,match='changed after preview'):
        service.execute_action(preview['ticket_id'])
    assert not runner.calls


def test_wrong_draft_hash_refused(make_service,monkeypatch):
    service,_,_ = make_service(mode='physical')
    values = attach(service,monkeypatch)
    values['draft_sha256']='f'*64
    with pytest.raises(WizardError): _ticket(service,'run_endpoint_trial',values)


@pytest.mark.parametrize('check',sorted(OPERATOR_CHECKS))
def test_every_operator_answer_is_explicit_and_required(make_service,monkeypatch,check):
    service,runner,_ = make_service(mode='physical')
    values = attach(service,monkeypatch)
    values[check] = False
    with pytest.raises(WizardError): _ticket(service,'run_endpoint_trial',values)
    assert service._endpoint_confirmation is None
    assert not runner.calls


def test_confirmation_failure_consumes_attachment_without_dispatch(make_service,monkeypatch):
    from rocell.application import endpoint_operator_confirmation as confirmation
    service,runner,_ = make_service(mode='physical')
    values = attach(service,monkeypatch)
    def refused(**kwargs): raise ValueError('Synthetic publication failure')
    monkeypatch.setattr(confirmation,'record_final_confirmation',refused)
    result = _run(service,'run_endpoint_trial',values)
    assert result['status'] == 'FAILED'
    assert service._endpoint_attempt_id == result['operation_id']
    assert service._endpoint_confirmation is None
    assert not runner.calls
    with pytest.raises(WizardError): _ticket(service,'run_endpoint_trial',values)


def test_acceptance_records_before_queue_and_duplicate_click_does_not_repeat(make_service,monkeypatch):
    service,_,_ = make_service(mode='physical')
    values = attach(service,monkeypatch)
    class DeferredExecutor:
        def __init__(self): self.calls = []
        def submit(self,*args): self.calls.append(args)
        def shutdown(self,**kwargs): pass
    executor = DeferredExecutor()
    service._executor = executor
    preview = _ticket(service,'run_endpoint_trial',values)
    receipt = service.execute_action(preview['ticket_id'])
    assert len(executor.calls) == 1
    confirmed = service._endpoint_confirmation[2]
    assert len(confirmed.operator_originals) == 7
    assert confirmed.request.to_dict()['attempt_id'] == receipt['operation_id']
    assert service.execute_action(preview['ticket_id'])['operation_id'] == receipt['operation_id']
    assert len(executor.calls) == 1


def test_refused_launch_exports_exact_confirmation(make_service,monkeypatch):
    from pathlib import Path
    from rocell.application.wizard_diagnostic_export import verify_export
    service,_,_ = make_service(mode='physical')
    values = attach(service,monkeypatch)
    monkeypatch.setattr(coordinator,'run_endpoint_draft',lambda *args,**kwargs:
        coordinator.EndpointRunOutcome('REVIEW_ISSUANCE_FAILED',None,None,None,'ValueError'))
    completed = _run(service,'run_endpoint_trial',values)
    assert completed['status'] == 'FAILED'
    event = next(e for e in service._log.events() if e['kind']=='endpoint_final_confirmation_recorded')
    assert event['details']['request_sha256'] == service._endpoint_confirmation[2].request.request_sha256
    assert len(event['details']['operator_reviews']) == 7
    exported = _run(service,'export_logs')
    assert exported['status'] == 'SUCCEEDED'
    assert verify_export(Path(exported['result']['receipt']['path']))['valid']
