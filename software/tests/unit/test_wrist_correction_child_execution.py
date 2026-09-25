from dataclasses import replace
from threading import Event
import pytest
from test_endpoint_current_context import fixture as endpoint_fixture
from test_wrist_correction_prelaunch import fixture as prelaunch_fixture
from test_wrist_correction_native_result import request_bytes
from rocell.providers.windows import wrist_correction_child_execution as module
from rocell.providers.windows import wrist_correction_prelaunch


def prepared(tmp_path,monkeypatch):
    _,snapshots,_,controller=endpoint_fixture()
    workspace,payload,directory=prelaunch_fixture(tmp_path,monkeypatch,controller.to_dict())
    monkeypatch.setattr(module,'load_host_wrist_correction_review_authority',wrist_correction_prelaunch.load_host_wrist_correction_review_authority)
    return workspace,payload,directory,snapshots


def test_child_reaches_fake_execution_after_original_checks(tmp_path,monkeypatch):
    workspace,payload,_,snapshots=prepared(tmp_path,monkeypatch)
    def metadata(**kwargs):
        assert kwargs['maximum_acquisitions']==8
        assert kwargs['deadline_ns']==payload['context']['deadline_ns']-2_000_000_000
        return lambda:replace(snapshots[0],started_monotonic_ns=3_000_000_000,finished_monotonic_ns=3_000_000_000)
    monkeypatch.setattr(module,'WindowsControllerMetadataAcquirer',metadata)
    monkeypatch.setattr(module.WindowsWristCorrectionSerialApi,'_load_kernel',lambda *_:pytest.fail('No native kernel allowed'))
    reached=[]
    def boundary(actual,permit,api,**kwargs):
        assert actual==payload and api.matches_authorization(permit._request,permit)
        assert kwargs['worker_claim'].claim_sha256
        reached.append(permit)
        return {'synthetic_boundary_reached':True}
    monkeypatch.setattr(module,'_execute_claimed_correction_trial',boundary)
    raw=request_bytes(payload)
    assert module.execute_correction_child(workspace,raw,cancellation=Event(),clock_ns=lambda:3_000_000_000)=={'synthetic_boundary_reached':True}
    assert len(reached)==1 and reached[0]._binding._state=='HELD'
    with pytest.raises(ValueError): module.execute_correction_child(workspace,raw,cancellation=Event(),clock_ns=lambda:3_000_000_000)
    assert len(reached)==1


@pytest.mark.parametrize('fault',['cancel','plan','controller','launch'])
def test_failure_before_metadata_cannot_reach_native(tmp_path,monkeypatch,fault):
    workspace,payload,directory,_=prepared(tmp_path,monkeypatch)
    monkeypatch.setattr(module,'WindowsControllerMetadataAcquirer',lambda **_:pytest.fail('Metadata must not be reached'))
    cancel=Event()
    if fault=='cancel': cancel.set()
    elif fault=='controller': (directory/'controller.original.json').write_bytes(b'{}')
    else:
        suffix='plan-review' if fault=='plan' else 'launch'
        (tmp_path/(payload['context']['attempt_id']+'-wrist-correction-'+suffix+'.json')).write_bytes(b'{}')
    with pytest.raises(ValueError):
        module.execute_correction_child(workspace,request_bytes(payload),cancellation=cancel,clock_ns=lambda:3_000_000_000)
