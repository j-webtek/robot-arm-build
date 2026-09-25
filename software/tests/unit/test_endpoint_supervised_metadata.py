"""Fixed diagnostic adapter tests with synthetic child output; no hardware."""

import json
from threading import Event
import pytest

from rocell.application import endpoint_supervised_metadata as module
from rocell.application.endpoint_trial_contract import EndpointTrialRequest, _canonical
from test_endpoint_current_context import fixture


def prepared(tmp_path,monkeypatch):
    context,snapshots,_,_ = fixture()
    body = context._request.to_dict()
    body['deadline_monotonic_ns'] = 31_000_000_000
    req = EndpointTrialRequest(_canonical(body))
    calls,retained = [],[]
    result = {'status':'SUCCEEDED','worker_exit_code':0,'physical_authority':False,
        'steps':[{'name':'native_arm_metadata_snapshot','exit_code':0,
                  'report':json.loads(snapshots[0].payload())}]}
    class Runner:
        def __init__(self,*args,**kwargs): pass
        def run(self,*args,**kwargs):
            calls.append((args,kwargs))
            return result
    monkeypatch.setattr(module,'DiagnosticProcessRunner',Runner)
    tick = [1_020_000_000]
    cancel = Event()
    factory = module.SupervisedEndpointMetadataFactory(workspace=tmp_path,
        source_sha256=body['references']['source_sha256'],cell_id='synthetic-test',
        cancellation_reader=lambda:cancel,retain=lambda record:retained.append(record),
        check_current=lambda:None,clock_ns=lambda:tick[0])
    return req,factory,result,calls,retained,tick,cancel


def test_reuses_fixed_metadata_action_and_preserves_child_time(tmp_path,monkeypatch):
    req,factory,_,calls,retained,_,_ = prepared(tmp_path,monkeypatch)
    acquire = factory(req)
    assert not calls
    snapshot = acquire()
    assert snapshot.started_monotonic_ns == 1_000_000_000
    assert len(calls) == 1 and calls[0][0] == ('inspect_native_arm_metadata',
        {'metadata_only':True,'power_disconnected':False})
    assert calls[0][1]['deadline_monotonic_ns'] == 4_000_000_000
    assert retained[0]['request_sha256'] == req.request_sha256


@pytest.mark.parametrize('fault',['timeout','bad_snapshot','exit','expired','cancelled','retention'])
def test_bad_or_late_metadata_never_becomes_context(tmp_path,monkeypatch,fault):
    req,factory,result,calls,retained,tick,cancel = prepared(tmp_path,monkeypatch)
    if fault == 'timeout': result['status'] = 'TIMED_OUT'
    if fault == 'bad_snapshot': result['steps'][0]['report'] = {}
    if fault == 'exit': result['worker_exit_code'] = 1
    if fault == 'expired': tick[0] = 4_000_000_000
    if fault == 'cancelled': cancel.set()
    if fault == 'retention': factory._retain = lambda record:False
    with pytest.raises(ValueError): factory(req)()
    assert len(calls) == (0 if fault in {'expired','cancelled'} else 1)


def test_supervision_exception_is_retained_without_retry(tmp_path,monkeypatch):
    req,factory,_,_,retained,_,_ = prepared(tmp_path,monkeypatch)
    def fail(*args,**kwargs): raise RuntimeError('Synthetic cleanup uncertainty')
    monkeypatch.setattr(factory._runner,'run',fail)
    with pytest.raises(RuntimeError): factory(req)()
    assert retained[0]['status'] == 'METADATA_SUPERVISION_FAILED'
    assert 'result' not in retained[0]


def test_expired_diagnostic_deadline_prevents_subprocess(tmp_path,monkeypatch):
    from rocell.application import wizard_diagnostic_coordinator as diagnostic
    monkeypatch.setattr(diagnostic.subprocess,'Popen',lambda *a,**k:pytest.fail('No child after deadline'))
    runner = diagnostic.DiagnosticProcessRunner(tmp_path,expected_source_sha256='a'*64)
    result = runner.run('inspect_native_arm_metadata',{'metadata_only':True,'power_disconnected':False},
        cell_id='synthetic-test',cancel=Event(),progress=lambda _:None,deadline_monotonic_ns=1)
    assert result['status'] == 'TIMED_OUT'


@pytest.mark.parametrize('retention_delay_ns',[20_000_000,120_000_000])
def test_actual_context_gate_includes_retention_delay(tmp_path,monkeypatch,retention_delay_ns):
    from rocell.providers.windows.endpoint_current_context import EndpointCurrentContextReader
    req,factory,_,_,retained,tick,_ = prepared(tmp_path,monkeypatch)
    _,_,_,binding = fixture()
    tick[0] = 1_000_000_000
    def retain(record):
        retained.append(record)
        tick[0] += retention_delay_ns
    factory._retain = retain
    context = EndpointCurrentContextReader(req,binding=binding,
        connection_id=req.to_dict()['attempt_id'],metadata_reader=factory(req),
        references_reader=lambda:tuple(sorted(req.to_dict()['references'].items())),
        clock_ns=lambda:tick[0])
    if retention_delay_ns > 100_000_000:
        with pytest.raises(ValueError,match='stale'): context()
    else:
        assert context().observed_ns == 1_000_000_000
    assert retained
