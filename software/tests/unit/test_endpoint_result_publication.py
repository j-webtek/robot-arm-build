"""Post-exit originals are retained even when endpoint result decoding fails."""

import base64
import json
import os
import hashlib
from dataclasses import replace
import pytest

from rocell.application import endpoint_worker_claim as claims
from rocell.providers.windows.endpoint_result_publication import publish_endpoint_result, publish_supervised_endpoint_result
from rocell.providers.windows.owned_worker_process import owned_request_wire
from test_endpoint_worker_claim import prepared
from test_endpoint_native_registration import registration
from test_endpoint_trial_execution import execute
from rocell.application.arm_bench_qualification_contract import _canonical
from rocell.application.endpoint_trial_contract import EndpointTrialRequest
from rocell.providers.windows.endpoint_native_wire import decode_request
from rocell.providers.windows.endpoint_native_result import encode_result
from rocell.providers.windows.owned_worker_process import OwnedWorkerResult


@pytest.mark.parametrize('change', [None,'pid','hash','runtime','time'])
def test_receipt_checks_owned_parent_facts_after_request_expiry(tmp_path,change):
    req,args,_ = prepared(tmp_path)
    claim = claims.claim_endpoint_worker(tmp_path,req,**args)
    kwargs = dict(claim_sha256=claim.claim_sha256,launch_sha256=args['launch_sha256'],
                  owned_process_id=os.getpid(),runtime_sha256=args['current_runtime_sha256'],
                  finished_ns=40_000_000_000)
    if change=='pid': kwargs['owned_process_id']+=1
    if change=='hash': kwargs['claim_sha256']='f'*64
    if change=='runtime': kwargs['runtime_sha256']='f'*64
    if change=='time': kwargs['finished_ns']=1
    if change:
        with pytest.raises(ValueError): claims.verify_endpoint_worker_receipt(tmp_path,req,**kwargs)
    else:
        receipt = claims.verify_endpoint_worker_receipt(tmp_path,req,**kwargs)
        assert receipt['replay_allowed'] is False


@pytest.mark.parametrize('stdout', [b'',b'not-json',b'{"status":"success"}'])
def test_invalid_and_empty_output_preserved_without_success(tmp_path,stdout):
    reg,outer = registration(tmp_path)
    raw,_ = owned_request_wire(reg,outer,deadline_ns=outer.expires_at_ns)
    output = tmp_path/'exports'
    output.mkdir()
    kwargs = dict(request_raw=raw,stdout=stdout,stderr=b'',owned_process_id=os.getpid(),
                  returncode=0,process_tree_closed=True,finished_ns=40_000_000_000)
    path,report = publish_endpoint_result(output,**kwargs)
    assert path.exists() and report['status']=='RESULT_REJECTED'
    stored = json.loads((output/report['originals']['stdout.bin']['file']).read_bytes())
    assert base64.b64decode(stored['base64'])==stdout
    assert report['replay_allowed'] is False
    with pytest.raises(Exception): publish_endpoint_result(output,**kwargs)


@pytest.mark.parametrize('closed,exitcode,status', [(True,0,'RESULT_RETAINED'),
    (False,0,'PROCESS_COMPLETION_UNCONFIRMED'),(True,1,'PROCESS_COMPLETION_UNCONFIRMED')])
def test_executor_to_retained_report_with_original_claim(tmp_path,monkeypatch,closed,exitcode,status):
    reg,outer = registration(tmp_path)
    payload = json.loads(outer.payload_json)
    req = EndpointTrialRequest(_canonical(payload['endpoint_request']))
    result,_ = execute(tmp_path,monkeypatch,request=req,
                       runtime_original=_canonical(payload['registration']))
    prefix = req.to_dict()['attempt_id']
    launch = (tmp_path/(prefix+'-endpoint-worker-launch.json')).read_bytes()
    claim = (tmp_path/(prefix+'-endpoint-worker-claimed.json')).read_bytes()
    payload['launch_sha256']=hashlib.sha256(launch).hexdigest()
    outer = replace(outer,payload_json=_canonical(payload))
    raw,_ = owned_request_wire(reg,outer,deadline_ns=outer.expires_at_ns)
    wire = decode_request(raw)
    stdout = encode_result({'schema':'rocell.endpoint_native_child_result.v1',
        'claim_sha256':hashlib.sha256(claim).hexdigest(),'execution':result,
        'physical_authority':False},wire)
    output = tmp_path/'exports'
    output.mkdir()
    _,report = publish_endpoint_result(output,request_raw=raw,stdout=stdout,stderr=b'',
        owned_process_id=os.getpid(),returncode=exitcode,process_tree_closed=closed,
        finished_ns=40_000_000_000)
    assert report['status']==status and report['errors']==[]
    assert report['summary']['endpoint_observed'] is True
    assert report['physical_movement_verified'] is False


@pytest.mark.parametrize('mismatch', [False,True])
def test_supervisor_adapter_retains_failed_bytes_and_rejects_cross_request(tmp_path,mismatch):
    reg,req = registration(tmp_path)
    _,digest = owned_request_wire(reg,req,deadline_ns=req.expires_at_ns)
    result = OwnedWorkerResult('FAILED','WORKER_EXIT_FAILED',(),digest,req.attempt_id,
        True,True,True,1,100,0,3,1,b'invalid output',b'child failure',
        owned_process_id=123,finished_monotonic_ns=40_000_000_000)
    if mismatch:
        result = replace(result,request_sha256='f'*64)
        with pytest.raises(ValueError):
            publish_supervised_endpoint_result(tmp_path,registration=reg,request=req,result=result)
    else:
        _,report = publish_supervised_endpoint_result(tmp_path,registration=reg,request=req,result=result)
        assert report['status']=='RESULT_REJECTED'
        assert report['originals']['stderr.bin']['bytes']==len(b'child failure')
