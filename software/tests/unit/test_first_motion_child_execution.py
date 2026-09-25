"""Child preparation/order tests; mocked native dependencies cannot open hardware."""
from threading import Event
from types import SimpleNamespace

import pytest

from rocell.providers.windows import first_motion_child_execution as module
from rocell.providers.windows.owned_worker_process import owned_request_wire
from test_first_motion_native_registration import registration


def test_precancel_stops_before_decoding(tmp_path,monkeypatch):
    monkeypatch.setattr(module,'decode_request',lambda *a:pytest.fail('Decode after cancellation'))
    event=Event(); event.set()
    with pytest.raises(ValueError): module.execute_first_motion_child(tmp_path,b'',cancellation=event)


def test_changed_source_stops_before_key_claim_metadata(tmp_path,monkeypatch):
    reg,outer=registration(tmp_path)
    raw,_=owned_request_wire(reg,outer,deadline_ns=outer.expires_at_ns)
    for name in ('load_host_first_motion_review_authority','claim_first_motion_worker','WindowsControllerMetadataAcquirer'):
        monkeypatch.setattr(module,name,lambda *a,**kw:pytest.fail('No authority/native access after bad references'))
    # tmp_path is not the source workspace from the request; actual reconstruction must refuse.
    with pytest.raises(Exception): module.execute_first_motion_child(tmp_path,raw,cancellation=Event())


@pytest.mark.parametrize('failure',[False,True])
def test_ordering_and_revocation_on_executor_failure(tmp_path,monkeypatch,failure):
    reg,outer=registration(tmp_path)
    raw,_=owned_request_wire(reg,outer,deadline_ns=outer.expires_at_ns)
    events=[]
    def mark(name,value):
        def call(*a,**kw): events.append(name); return value
        return call
    monkeypatch.setattr(module,'FirstMotionReferenceReader',lambda *a,**kw:mark('refs',(('source_sha256','a'*64),)))
    monkeypatch.setattr(module,'decode_controller_binding',mark('binding',SimpleNamespace(identity=SimpleNamespace(port_name='COM7'))))
    monkeypatch.setattr(module,'load_host_first_motion_review_authority',mark('key',object()))
    monkeypatch.setattr(module,'claim_first_motion_worker',mark('claim',SimpleNamespace(claim_sha256='c'*64)))
    monkeypatch.setattr(module,'WindowsControllerMetadataAcquirer',mark('metadata',object()))
    monkeypatch.setattr(module,'FirstMotionCurrentContextReader',mark('context',object()))
    monkeypatch.setattr(module,'AuthenticatedFirstMotionReviewReader',mark('reviews',object()))
    permit=SimpleNamespace(revoke=mark('revoke',None))
    monkeypatch.setattr(module,'authorize_first_motion',mark('authorize',permit))
    monkeypatch.setattr(module,'WindowsFirstMotionSerialApi',SimpleNamespace(from_first_motion_permit=mark('facade',object())))
    def execute(*a,**kw):
        events.append('execute')
        if failure: raise RuntimeError('synthetic failure')
        return {'status':'SYNTHETIC_ORDER_TEST_ONLY'}
    monkeypatch.setattr(module,'execute_native_first_motion_trial',execute)
    if failure:
        with pytest.raises(RuntimeError): module.execute_first_motion_child(tmp_path,raw,cancellation=Event(),clock_ns=lambda:2_000_000_000)
    else:
        result=module.execute_first_motion_child(tmp_path,raw,cancellation=Event(),clock_ns=lambda:2_000_000_000)
        assert result['physical_authority'] is False
    assert events==['refs','binding','key','claim','metadata','context','reviews','authorize','facade','execute','revoke']
