"""Synthetic final answers through real retained request/review coordination."""

import pytest
from rocell.application.endpoint_operator_confirmation import record_final_confirmation
from rocell.application import wizard_endpoint_coordinator as coordinator
from rocell.safety.bench_review_authority import OPERATOR_CHECKS
from test_wizard_endpoint_draft_launch import setup


def confirmation(draft,kwargs,**changes):
    args = dict(draft=draft,expected_draft_sha256=draft.draft_sha256,
        attempt_id=kwargs['attempt_id'],actor_id='synthetic-operator',
        answers=dict.fromkeys(OPERATOR_CHECKS,True),root=kwargs['review_root'],
        deadline_ns=31_000_000_000,check_current=kwargs['check_current'],clock_ns=kwargs['clock_ns'])
    args.update(changes)
    return record_final_confirmation(**args)


def test_final_answers_bound_to_same_request_used_by_coordinator(tmp_path,monkeypatch):
    workspace,draft,kwargs,calls = setup(tmp_path,monkeypatch)
    confirmed = confirmation(draft,kwargs)
    kwargs['operator_reader'] = confirmed.intake.operator_reader
    result = coordinator.run_endpoint_draft(workspace,draft,
        prepared_request=confirmed.request,**kwargs)
    assert result.stage == 'TEST_NO_NATIVE_WORKER'
    assert len(calls) == 1 and calls[0].canonical_bytes == confirmed.request.canonical_bytes
    retained = next(tmp_path.glob('*-endpoint-confirmed-request.json')).read_bytes()
    assert retained == next(tmp_path.glob('*-endpoint-draft-request.json')).read_bytes()
    assert len(list(tmp_path.glob('*-review-original.json'))) == 7
    with pytest.raises(Exception): confirmation(draft,kwargs)


@pytest.mark.parametrize('fault',['missing','false','numeric','actor','draft','cancelled'])
def test_incomplete_or_changed_confirmation_never_records_request(tmp_path,monkeypatch,fault):
    _,draft,kwargs,_ = setup(tmp_path,monkeypatch)
    answers = dict.fromkeys(OPERATOR_CHECKS,True)
    changes = {}
    if fault == 'missing': answers.pop('operator_present')
    if fault == 'false': answers['operator_present'] = False
    if fault == 'numeric': answers['operator_present'] = 1
    if fault == 'actor': changes['actor_id'] = '../invalid'
    if fault == 'draft': changes['expected_draft_sha256'] = 'f'*64
    if fault == 'cancelled': changes['check_current'] = lambda:'cancelled'
    with pytest.raises(ValueError): confirmation(draft,kwargs,answers=answers,**changes)
    assert not list(tmp_path.glob('*-endpoint-confirmed-request.json'))
    assert not list(tmp_path.glob('*-review-original.json'))


@pytest.mark.parametrize('fault',['deadline','attempt','delayed'])
def test_prepared_confirmation_cannot_renew_or_change_attempt(tmp_path,monkeypatch,fault):
    workspace,draft,kwargs,calls = setup(tmp_path,monkeypatch)
    confirmed = confirmation(draft,kwargs)
    kwargs['operator_reader'] = confirmed.intake.operator_reader
    if fault == 'attempt': kwargs['attempt_id'] = 'operation-'+'e'*32
    if fault == 'deadline': kwargs['deadline_ns'] = 30_000_000_000
    if fault == 'delayed': kwargs['clock_ns'] = lambda:5_000_000_000
    result = coordinator.run_endpoint_draft(workspace,draft,prepared_request=confirmed.request,**kwargs)
    assert result.stage == ('REVIEW_BUDGET_FAILED' if fault=='delayed' else 'DRAFT_VALIDATION_FAILED')
    assert not calls
    assert next(tmp_path.glob('*-endpoint-confirmed-request.json')).read_bytes() == confirmed.request.canonical_bytes
