"""Real child composition with fake OS metadata/I/O and synthetic approvals.

Source/build and retained files are actually read. No physical arm is accessed;
synthetic clock values do not qualify real host latency or movement.
"""

import ctypes
import base64
from dataclasses import replace
import hashlib
import json
from pathlib import Path
from threading import Event
import pytest

from rocell.providers.windows import endpoint_child_execution as child
from rocell.providers.windows.nonpurging_serial_api import WindowsNativeSerialApi
from rocell.providers.windows.owned_worker_process import owned_request_wire,owned_registration_document
from rocell.providers.windows.endpoint_native_wire import decode_request
from rocell.providers.windows.endpoint_native_result import encode_result,decode_result
from rocell.application import endpoint_reference_reader as refs
from rocell.application.endpoint_trial_contract import EndpointTrialRequest
from rocell.application.endpoint_evidence_snapshot import SCHEMA as SNAPSHOT_SCHEMA,FILENAME
from rocell.application.endpoint_worker_claim import reserve_endpoint_launch
from rocell.application.arm_bench_qualification_contract import _canonical
from rocell.application.physical_connection_contracts import _canonical_bytes
from rocell.application.physical_onboarding_durability import publish_bytes,PublicationMode
from rocell.safety.bench_review_authority import BenchReviewAuthority
from test_bench_review_authority import originals
from test_endpoint_native_registration import registration
from test_endpoint_current_context import fixture as context_fixture
from test_endpoint_serial_connection import OwnerKernel


@pytest.mark.parametrize('fault',['none','baseline','unchanged','slow-references','metadata-delay','metadata-too-slow'])
def test_child_to_result_with_owned_native_boundary(tmp_path,monkeypatch,fault):
    workspace = Path(__file__).resolve().parents[3]
    reg,outer = registration(tmp_path)
    payload = json.loads(outer.payload_json)
    data = payload['endpoint_request']
    _,snapshots,_,binding = context_fixture()
    data['references']['source_sha256']=refs.source_fingerprint(workspace)
    data['references']['build_snapshot_sha256']=refs.import_build_snapshot(workspace).snapshot_hash
    for name in refs.ORIGINAL_REFERENCES:
        raw = (_canonical_bytes(binding.to_dict()) if name=='native_controller_review_sha256'
               else _canonical({'schema':'test.synthetic.original.v1','reference':name}))
        data['references'][name]=hashlib.sha256(raw).hexdigest()
        publish_bytes(tmp_path,data['attempt_id']+'-'+name+'.original.json',raw,mode=PublicationMode.IMMUTABLE)
    for name in ('source_sha256','configuration_sha256','geometry_sha256','firmware_review_sha256'):
        data['campaign']['evidence'][name]=data['references'][name]
    req = EndpointTrialRequest(_canonical(data))
    snapshot_raw = _canonical({'schema':SNAPSHOT_SCHEMA,'request':req.to_dict(),
        'request_sha256':req.request_sha256,'build_snapshot':refs.import_build_snapshot(workspace).to_dict(),
        'originals':{name:base64.b64encode((tmp_path/(data['attempt_id']+'-'+name+'.original.json')).read_bytes()).decode('ascii')
                     for name in refs.ORIGINAL_REFERENCES},'physical_authority':False})
    publish_bytes(reg.working_directory,FILENAME,snapshot_raw,mode=PublicationMode.REPLACE)
    reg = replace(reg,package_files=(*reg.package_files[:2],replace(reg.package_files[2],sha256=hashlib.sha256(snapshot_raw).hexdigest())))
    payload['registration']=owned_registration_document(reg)
    authority = BenchReviewAuthority(b'test-only-end-to-end-review-key!!')
    bundle = authority.seal(req,originals(req),now_ns=1_000_000_000)
    publish_bytes(tmp_path,data['attempt_id']+'-bench-reviews.json',bundle,mode=PublicationMode.IMMUTABLE)
    payload['launch_sha256']=reserve_endpoint_launch(tmp_path,req,
        runtime_original=_canonical(payload['registration']),
        review_bundle_sha256=hashlib.sha256(bundle).hexdigest(),now_ns=1_000_000_000)
    payload['endpoint_request']=req.to_dict()
    outer = replace(outer,source_sha256=data['references']['source_sha256'],
                    operation_sha256=req.request_sha256,payload_json=_canonical(payload))
    raw,_ = owned_request_wire(reg,outer,deadline_ns=outer.expires_at_ns)
    tick,completed,post_clocks = [1_000_000_000],[None],[0]
    if fault=='slow-references':
        original_references = refs.EndpointReferenceReader.__call__
        def delayed_references(reader):
            observed = original_references(reader)
            # Measured host source/build cost was 184 ms; model it explicitly
            # rather than letting the synthetic clock hide the stale baseline.
            tick[0]+=184_000_000
            return observed
        monkeypatch.setattr(refs.EndpointReferenceReader,'__call__',delayed_references)
    kernel = OwnerKernel()
    last_read = [None]
    kernel.input = b'x'*256
    def clock():
        if completed[0] is not None:
            post_clocks[0]+=1
            if post_clocks[0]==2: tick[0]+=1
        return tick[0]
    def metadata():
        started = tick[0]
        if fault=='metadata-delay': tick[0]+=47_000_000
        if fault=='metadata-too-slow': tick[0]+=60_000_000
        return replace(snapshots[0],started_monotonic_ns=started,finished_monotonic_ns=tick[0])
    monkeypatch.setattr(child,'WindowsControllerMetadataAcquirer',lambda **k:metadata)
    monkeypatch.setattr(child,'load_host_bench_review_authority',lambda _:authority)
    def read(handle,buffer,size,count,overlapped):
        step = 50_000_000
        if completed[0] is not None:
            remaining = completed[0]+2_000_000_000-tick[0]
            step = min(step,remaining,max(1,remaining//1_000_000)*1_000_000)
        tick[0]+=step
        last_read[0]=tick[0]
        x = 4 if fault=='baseline' else (1 if kernel.writes and fault!='unchanged' else 0)
        line = _canonical(dict(T=1051,x=x,y=0,z=0,tit=0,r=0,g=0,b=0,s=0,e=0,t=0))+b'\n'
        ctypes.memmove(buffer,line,len(line))
        kernel.size=len(line)
        return True
    original_write = kernel.WriteFile
    def write(*args):
        tick[0]+=1
        assert last_read[0] is not None and tick[0]-last_read[0]<=100_000_000
        completed[0]=tick[0]
        return original_write(*args)
    kernel.ReadFile,kernel.WriteFile=read,write
    def load(api):
        api._dll=kernel
        return kernel
    monkeypatch.setattr(WindowsNativeSerialApi,'_load_kernel',load)
    result = child.execute_endpoint_child(workspace,raw,cancellation=Event(),clock_ns=clock)
    if fault=='metadata-too-slow':
        assert kernel.writes==[],result
        assert result['execution']['status']!='OBSERVED_ENDPOINT_DWELL'
        assert kernel.closed==[202,201,101]
        return
    expected = {'none':'OBSERVED_ENDPOINT_DWELL','metadata-delay':'OBSERVED_ENDPOINT_DWELL','slow-references':'OBSERVED_ENDPOINT_DWELL','baseline':'HELD_BEFORE_WRITE',
                'unchanged':'INSUFFICIENT_ENDPOINT_EVIDENCE'}[fault]
    assert result['execution']['status']==expected,result
    assert len(kernel.writes)==(0 if fault=='baseline' else 1)
    assert kernel.closed==[202,201,101]
    wire = decode_request(raw)
    assert decode_result(encode_result(result,wire),wire=wire)['physical_authority'] is False
