"""Child preparation checks never access a device in these tests."""

from threading import Event
from types import SimpleNamespace
from dataclasses import replace
import pytest
from rocell.providers.windows import endpoint_child_execution as module
from rocell.application.endpoint_trial_contract import EndpointTrialRequest
from rocell.application.arm_bench_qualification_contract import _canonical
from rocell.application.physical_connection_contracts import _canonical_bytes
from rocell.application.physical_onboarding_durability import publish_bytes, PublicationMode
from test_endpoint_trial_contract import request
from test_endpoint_current_context import fixture
from test_endpoint_native_registration import registration
from rocell.providers.windows.owned_worker_process import owned_request_wire


def test_retained_controller_restores_exact_semantics(tmp_path):
    _,_,_,binding = fixture()
    data = request().to_dict()
    data['references']['native_controller_review_sha256']=binding.binding_sha256
    req = EndpointTrialRequest(_canonical(data))
    filename = data['attempt_id']+'-native_controller_review_sha256.original.json'
    publish_bytes(tmp_path,filename,_canonical_bytes(binding.to_dict()),mode=PublicationMode.IMMUTABLE)
    assert module.load_controller_binding(tmp_path,req)==binding
    publish_bytes(tmp_path,filename,b'{"changed":true}',mode=PublicationMode.REPLACE)
    with pytest.raises(ValueError): module.load_controller_binding(tmp_path,req)


def test_precancel_does_not_even_decode_request(tmp_path,monkeypatch):
    monkeypatch.setattr(module,'decode_request',lambda *a:pytest.fail('Must stop before decode'))
    cancel = Event()
    cancel.set()
    with pytest.raises(ValueError): module.execute_endpoint_child(tmp_path,b'',cancellation=cancel)


def test_missing_originals_prevent_claim_key_or_metadata_access(tmp_path,monkeypatch):
    reg,outer = registration(tmp_path)
    raw,_ = owned_request_wire(reg,outer,deadline_ns=outer.expires_at_ns)
    for name in ('claim_endpoint_worker','load_host_bench_review_authority','WindowsControllerMetadataAcquirer'):
        monkeypatch.setattr(module,name,lambda *a,**k:pytest.fail('No admission after missing originals'))
    with pytest.raises(Exception):
        module.execute_endpoint_child(tmp_path,raw,cancellation=Event())


@pytest.mark.parametrize('failure',[False,True])
def test_fixed_composition_orders_dependencies_and_always_revokes(tmp_path,monkeypatch,failure):
    reg,outer = registration(tmp_path)
    raw,_ = owned_request_wire(reg,outer,deadline_ns=outer.expires_at_ns)
    events = []
    def mark(name,value):
        def call(*a,**k):
            events.append(name)
            return value
        return call
    monkeypatch.setattr(module,'EndpointReferenceReader',lambda *a,**k:mark('references',(('source_sha256','a'*64),)))
    binding = SimpleNamespace(identity=SimpleNamespace(port_name='COM7'))
    monkeypatch.setattr(module,'decode_controller_binding',mark('binding',binding))
    monkeypatch.setattr(module,'load_host_bench_review_authority',mark('key',object()))
    monkeypatch.setattr(module,'claim_endpoint_worker',mark('claim',SimpleNamespace(claim_sha256='c'*64)))
    monkeypatch.setattr(module,'WindowsControllerMetadataAcquirer',mark('metadata-construct',object()))
    monkeypatch.setattr(module,'EndpointCurrentContextReader',mark('context-construct',object()))
    monkeypatch.setattr(module,'AuthenticatedBenchReviewReader',mark('reviews-construct',SimpleNamespace(presence_expiry=lambda:20_000_000_000)))
    permit = SimpleNamespace(revoke=mark('revoke',None))
    monkeypatch.setattr(module,'authorize_bench_endpoint',mark('authorize',permit))
    monkeypatch.setattr(module,'WindowsEndpointSerialApi',SimpleNamespace(from_bench_permit=mark('facade',object())))
    def execute(*a,**k):
        events.append('execute')
        assert k['presence_expiry_reader']()==20_000_000_000
        if failure: raise RuntimeError('synthetic executor failure')
        return {'status':'SYNTHETIC_ORDERING_TEST_ONLY'}
    monkeypatch.setattr(module,'execute_native_endpoint_trial',execute)
    if failure:
        with pytest.raises(RuntimeError): module.execute_endpoint_child(tmp_path,raw,cancellation=Event(),clock_ns=lambda:1_000_000_000)
    else:
        result = module.execute_endpoint_child(tmp_path,raw,cancellation=Event(),clock_ns=lambda:1_000_000_000)
        assert result['physical_authority'] is False
    assert events==['references','binding','key','claim','metadata-construct','context-construct',
                    'reviews-construct','authorize','facade','execute','revoke']
