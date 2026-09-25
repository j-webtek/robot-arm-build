"""Native wrapper failure/cancellation checks through fake kernel composition."""
import hashlib
from threading import Event

import pytest

from rocell.application.first_motion_worker_claim import reserve_first_motion_launch, claim_first_motion_worker
from rocell.providers.windows.first_motion_trial_execution import execute_native_first_motion_trial
from test_first_motion_serial_connection import owner


@pytest.mark.parametrize('fault',['cancelled','setup','runtime'])
def test_claim_before_open_and_cleanup_without_retry(tmp_path,monkeypatch,fault):
    request,permit,_,kernel,clock,api = owner(tmp_path,monkeypatch)
    runtime=b'{"worker":"synthetic-only"}'
    runtime_sha=hashlib.sha256(runtime).hexdigest()
    review=tmp_path/(request.to_dict()['attempt_id']+'-first-motion-reviews.json')
    source=request.to_dict()['references']['source_sha256']
    launch=reserve_first_motion_launch(tmp_path,request,runtime_original=runtime,
        review_bundle_sha256=hashlib.sha256(review.read_bytes()).hexdigest(),now_ns=clock[0])
    claim=claim_first_motion_worker(tmp_path,request,launch_sha256=launch,
        current_source_sha256=source,current_runtime_sha256=runtime_sha,now_ns=clock[0])
    event=Event()
    if fault=='cancelled': event.set()
    if fault=='setup': kernel.fail_setup=True
    kwargs=dict(cancellation=event,worker_claim=claim,current_source_sha256=source,
        current_runtime_sha256='f'*64 if fault=='runtime' else runtime_sha,clock_ns=lambda:clock[0])
    if fault=='runtime':
        with pytest.raises(ValueError): execute_native_first_motion_trial(request,permit,api,**kwargs)
        assert api._dll is None
    else:
        result=execute_native_first_motion_trial(request,permit,api,**kwargs)
        assert result['status']==('CANCELLED_BEFORE_OPEN' if fault=='cancelled' else 'NATIVE_TRIAL_FAILED')
        assert result['lifecycle']['owned_handle_count']==0
        assert kernel.closed==([] if fault=='cancelled' else [202,201,101])
    assert kernel.writes==[]
    kwargs['current_runtime_sha256']=runtime_sha
    with pytest.raises(ValueError): execute_native_first_motion_trial(request,permit,api,**kwargs)
