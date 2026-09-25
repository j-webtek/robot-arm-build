"""Validate real executor output using fake native I/O, never physical hardware."""

import copy
import pytest

from rocell.application.endpoint_trial_contract import EndpointTrialRequest
from rocell.application.arm_bench_qualification_contract import _canonical
from rocell.providers.windows.endpoint_native_result import encode_result, decode_result, validate_result
from rocell.providers.windows.endpoint_native_wire import decode_request
from rocell.providers.windows.owned_worker_process import owned_request_wire
from test_endpoint_native_registration import registration
from test_endpoint_trial_execution import execute


def result_fixture(tmp_path, monkeypatch, **fault):
    reg, outer = registration(tmp_path)
    raw, _ = owned_request_wire(reg,outer,deadline_ns=outer.expires_at_ns)
    wire = decode_request(raw)
    req = EndpointTrialRequest(_canonical(wire['payload']['endpoint_request']))
    execution, kernel = execute(tmp_path,monkeypatch,request=req,**fault)
    child = {'schema':'rocell.endpoint_native_child_result.v1','claim_sha256':'c'*64,
             'execution':execution,'physical_authority':False}
    return decode_result(encode_result(child,wire),wire=wire),wire,kernel


@pytest.mark.parametrize('fault', [{},{'cancel':True},{'wrong_baseline':True}],
                         ids=['endpoint','cancel-before-open','baseline-mismatch'])
def test_executor_results_round_trip_without_physical_claims(tmp_path,monkeypatch,fault):
    value,wire,kernel = result_fixture(tmp_path,monkeypatch,**fault)
    summary = validate_result(value,wire=wire)
    assert summary['endpoint_observed'] is (not fault)
    assert summary['physical_movement_verified'] is False
    assert len(kernel.writes) == (0 if fault else 1)


@pytest.mark.parametrize('field', ['request','raw','coverage','analysis','write','cleanup','authority'])
def test_changed_or_contradictory_evidence_is_rejected(tmp_path,monkeypatch,field):
    value,wire,_ = result_fixture(tmp_path,monkeypatch)
    changed = copy.deepcopy(value)
    execution = changed['child_result']['execution']
    trial = execution['trial']
    if field=='request': changed['request_sha256']='f'*64
    elif field=='raw': trial['post']['raw']['sha256']='f'*64
    elif field=='coverage': trial['post']['coverage']={}
    elif field=='analysis': trial['analysis']['status']='INSUFFICIENT_ENDPOINT_EVIDENCE'
    elif field=='write': trial['write']['confirmed_write_bytes']=0
    elif field=='cleanup': execution['lifecycle']['pending_io_count']=1
    elif field=='authority': execution['physical_movement_verified']=True
    with pytest.raises(ValueError): validate_result(changed,wire=wire)
