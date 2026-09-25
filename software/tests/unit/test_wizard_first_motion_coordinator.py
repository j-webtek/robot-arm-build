"""Coordinator sequencing with incapable preparation/worker/publication doubles."""
from threading import Event
from types import SimpleNamespace

import pytest

from rocell.application import wizard_first_motion_coordinator as module
from test_first_motion_measurement_binding import setup,SESSION,OPERATION


@pytest.mark.parametrize('fault',[None,'preparation','authorization','retention','cancel-after'])
def test_single_attempt_and_retention_failure_keeps_owned_result(tmp_path,monkeypatch,fault):
    _,request=setup(tmp_path)
    calls=[]; event=Event()
    prepared=SimpleNamespace(registration=object(),request=SimpleNamespace(expires_at_ns=32_000_000_000))
    owned=object()
    def prepare(*a,**kw):
        calls.append('prepare')
        assert kw['measurement_operation_id']==OPERATION
        if fault=='preparation': raise ValueError('synthetic failure')
        return prepared
    monkeypatch.setattr(module,'prepare_first_motion_worker',prepare)
    monkeypatch.setattr(module,'owned_request_wire',lambda *a,**kw:(b'wire','a'*64))
    class Worker:
        def __init__(self,reg,*,authorizer): self.authorizer=authorizer
        def run(self,outer,**kw):
            self.authorizer(prepared.registration,outer,'f'*64 if fault=='authorization' else 'a'*64)
            calls.append('run')
            if fault=='cancel-after': event.set()
            return owned
    monkeypatch.setattr(module,'OwnedWindowsWorker',Worker)
    def publish(root,**kwargs):
        calls.append('retain')
        assert kwargs['result'] is owned
        if fault=='retention': raise OSError('synthetic retention failure')
        return tmp_path/'report.json',{'status':'SYNTHETIC_ONLY'}
    monkeypatch.setattr(module,'publish_supervised_first_motion_result',publish)
    result=module.run_reviewed_first_motion(tmp_path,request,review_root=tmp_path,export_root=tmp_path,
        session_id=SESSION,measurement_operation_id=OPERATION,cancellation=event,
        check_current=lambda:None,clock_ns=lambda:2_000_000_000)
    expected={'preparation':'PREPARATION_FAILED','authorization':'SUPERVISION_FAILED','retention':'RETENTION_FAILED'}
    assert result.stage==expected.get(fault,'RETAINED')
    assert calls.count('run')<=1 and calls.count('retain')<=1
    if fault in {None,'retention','cancel-after'}: assert result.owned is owned
    if fault=='cancel-after': assert calls==['prepare','run','retain']


def test_precancel_stops_before_preparation(tmp_path,monkeypatch):
    _,request=setup(tmp_path)
    event=Event(); event.set()
    monkeypatch.setattr(module,'prepare_first_motion_worker',lambda *a,**kw:pytest.fail('Cancelled preparation'))
    result=module.run_reviewed_first_motion(tmp_path,request,review_root=tmp_path,export_root=tmp_path,
        session_id=SESSION,measurement_operation_id=OPERATION,cancellation=event,
        check_current=lambda:None,clock_ns=lambda:2_000_000_000)
    assert result.stage=='PREPARATION_FAILED' and result.owned is None


@pytest.mark.parametrize('fault', [None, 'reviews', 'confirm', 'measurement', 'stage', 'cancel-before-run'])
def test_final_click_pipeline_stops_at_failure_and_preserves_execution_outcome(tmp_path, monkeypatch, fault):
    """Incapable doubles exercise the host orchestration, not hardware admission."""
    from rocell.application.first_motion_draft import FirstMotionDraft
    _, request = setup(tmp_path)
    draft = FirstMotionDraft.from_request(request)
    event = Event()
    calls = []
    owned = object()
    outcome = module.FirstMotionRunOutcome('RETENTION_FAILED', owned, None, None, 'OSError')
    def step(name, result):
        def run(*args, **kwargs):
            calls.append(name)
            if 'check_current' in kwargs: kwargs['check_current']()
            if fault == name: raise ValueError('Synthetic failure')
            if name == 'stage' and fault == 'cancel-before-run': event.set()
            return result
        return run
    monkeypatch.setattr(module, 'load_selected_reviews', step('reviews', {}))
    monkeypatch.setattr(module, 'load_host_first_motion_review_authority', step('key', object()))
    monkeypatch.setattr(module, 'confirm_draft', step('confirm', (request, {})))
    monkeypatch.setattr(module, 'load_measurement_for_request', step('measurement', (b'original', {})))
    monkeypatch.setattr(module, 'stage_first_motion_originals', step('stage', {}))
    monkeypatch.setattr(module, 'run_reviewed_first_motion', step('run', outcome))
    result = module.run_confirmed_first_motion(tmp_path, draft, {},
        attempt_id=request.to_dict()['attempt_id'], reference_originals={}, review_selections=(),
        review_root=tmp_path, export_root=tmp_path, session_id=SESSION,
        measurement_operation_id=OPERATION, cancellation=event,
        check_current=lambda: None, clock_ns=lambda: 2_000_000_000)
    sequence = ['reviews', 'key', 'confirm', 'measurement', 'stage', 'run']
    if fault is None:
        assert result is outcome and result.owned is owned
        assert calls == sequence
    else:
        last = 'stage' if fault == 'cancel-before-run' else fault
        assert calls == sequence[:sequence.index(last)+1]
        assert result.owned is None and result.stage.endswith('_FAILED')
