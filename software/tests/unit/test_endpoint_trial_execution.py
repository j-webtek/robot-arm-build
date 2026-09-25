"""Full native composition through fake Windows calls and synthetic poses."""

import ctypes
from dataclasses import replace
import json
import hashlib
from threading import Event

from rocell.providers.windows.endpoint_serial_api import WindowsEndpointSerialApi
from rocell.providers.windows.endpoint_trial_execution import execute_native_endpoint_trial
from rocell.providers.windows.nonpurging_serial_api import WindowsNativeSerialApi
from rocell.safety.bench_endpoint import authorize_bench_endpoint
from rocell.application.endpoint_worker_claim import reserve_endpoint_launch, claim_endpoint_worker
from test_bench_review_authority import fixture
from test_endpoint_serial_connection import OwnerKernel


def execute(tmp_path,monkeypatch,*,cancel=False,wrong_baseline=False,request=None,runtime_original=None):
    req,authority,records,raw,filename,reader,tick,current = fixture(tmp_path,request)
    current[0] = replace(current[0],port_name='COM7')
    runtime = b'{"worker":"synthetic-test-only"}' if runtime_original is None else runtime_original
    runtime_sha = hashlib.sha256(runtime).hexdigest()
    source_sha = req.to_dict()['references']['source_sha256']
    launch_sha = reserve_endpoint_launch(tmp_path,req,runtime_original=runtime,
        review_bundle_sha256=hashlib.sha256(raw).hexdigest(),now_ns=tick[0])
    claim = claim_endpoint_worker(tmp_path,req,launch_sha256=launch_sha,
        current_source_sha256=source_sha,current_runtime_sha256=runtime_sha,now_ns=tick[0])
    permit = authorize_bench_endpoint(req,connection_id='owned-test',evidence_reader=reader,
                                     attempt_root=tmp_path,clock=lambda:tick[0])
    kernel = OwnerKernel()
    kernel.input = b'x'*256  # Fake queue availability; ReadFile supplies pose bytes.
    completed, post_clocks = [None], [0]
    def clock():
        if completed[0] is not None:
            post_clocks[0] += 1
            if post_clocks[0] == 2: tick[0] += 1
        return tick[0]
    def read(handle,buffer,size,count,overlapped):
        step = 50_000_000
        if completed[0] is not None:
            remaining = completed[0]+2_000_000_000-tick[0]
            step = min(step,remaining,max(1,remaining//1_000_000)*1_000_000)
        tick[0] += step
        current[0] = replace(current[0],observed_ns=tick[0])
        x = 4 if wrong_baseline else (1 if kernel.writes else 0)
        data = json.dumps(dict(T=1051,x=x,y=0,z=0,tit=0,r=0,g=0,b=0,s=0,e=0,t=0),separators=(',',':')).encode()+b'\n'
        ctypes.memmove(buffer,data,len(data))
        kernel.size = len(data)
        return True
    original_write = kernel.WriteFile
    def write(*args):
        tick[0] += 1
        completed[0] = tick[0]
        return original_write(*args)
    kernel.ReadFile, kernel.WriteFile = read, write
    def load(api):
        api._dll = kernel
        return kernel
    monkeypatch.setattr(WindowsNativeSerialApi,'_load_kernel',load)
    api = WindowsEndpointSerialApi.from_bench_permit(req,permit,port_name='COM7',connection_id='owned-test')
    event = Event()
    if cancel: event.set()
    result = execute_native_endpoint_trial(req,permit,api,cancellation=event,
        presence_expiry_reader=lambda:req.to_dict()['deadline_monotonic_ns'],clock_ns=clock,
        worker_claim=claim,current_source_sha256=source_sha,current_runtime_sha256=runtime_sha)
    assert not result['physical_movement_verified'] and not result['physical_stop_verified']
    return result,kernel


def test_admitted_open_baseline_write_endpoint_close_composition(tmp_path,monkeypatch):
    result,kernel = execute(tmp_path,monkeypatch)
    assert result['status'] == 'OBSERVED_ENDPOINT_DWELL', result['trial']['analysis']
    assert len(kernel.writes)==1 and kernel.closed == [202,201,101]
    assert result['lifecycle']['phase']=='CLOSED'
    assert result['trial']['baseline']['raw']['bytes'] > 0
    assert result['trial']['post']['raw']['bytes'] > 0


def test_cancellation_before_open_has_no_kernel_effects(tmp_path,monkeypatch):
    result,kernel = execute(tmp_path,monkeypatch,cancel=True)
    assert result['status']=='CANCELLED_BEFORE_OPEN'
    assert kernel.writes == kernel.closed == []


def test_bad_baseline_closes_without_motion_submission(tmp_path,monkeypatch):
    result,kernel = execute(tmp_path,monkeypatch,wrong_baseline=True)
    assert result['status']=='HELD_BEFORE_WRITE'
    assert kernel.writes==[] and kernel.closed==[202,201,101]
