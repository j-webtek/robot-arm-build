from dataclasses import replace
import json
import pytest
from test_wrist_correction_parent_review import run
from rocell.providers.windows.wrist_correction_native_protocol import decode_request
from rocell.providers.windows.owned_worker_process import OwnedWorkerResult
from rocell.application import wrist_correction_process_finalization as finalization


def inputs(tmp_path,monkeypatch,bias=.87):
    raw,args,kernel=run(tmp_path,monkeypatch,bias=bias)
    request=args['request_raw'];wire=decode_request(request)
    process=OwnedWorkerResult(status='SUCCEEDED',primary_error=None,cleanup_errors=(),
        request_sha256=wire['request_sha256'],attempt_id=wire['attempt_id'],process_created=True,
        initial_thread_resumed=True,tree_exit_confirmed=True,returncode=0,
        elapsed_ns=args['process_finished_ns']-args['process_started_ns'],stdin_bytes_written=len(request),
        peak_observed_handles=10,peak_active_processes=1,stdout=raw,stderr=b'',
        owned_process_id=args['owned_process_id'],finished_monotonic_ns=args['process_finished_ns'])
    params={k:args[k] for k in ('assigned_root','authority','process_started_ns')}
    return request,process,params,kernel


@pytest.mark.parametrize('bias,status',[(.87,'REPORTED_SETTLED'),(0,'WRIST_EXCURSION')])
def test_retention_and_parent_reconstruction(tmp_path,monkeypatch,bias,status):
    request,process,args,kernel=inputs(tmp_path,monkeypatch,bias)
    result=finalization.finalize_correction_process(request,process,**args)
    assert result['status']==status and result['review']['reported_endpoint_reconstructed']
    assert not result['campaign_advance_allowed'] and len(kernel.writes)==1
    assert (tmp_path/result['parent_original']['file']).is_file()
    assert (tmp_path/result['verdict_retention']['file']).is_file()


@pytest.mark.parametrize('fault',['timeout','cleanup','short_input','malformed_output'])
def test_failures_retained_without_false_success(tmp_path,monkeypatch,fault):
    request,process,args,_=inputs(tmp_path,monkeypatch)
    if fault=='timeout': process=replace(process,status='TIMED_OUT',primary_error='TIMED_OUT')
    if fault=='cleanup': process=replace(process,tree_exit_confirmed=False,cleanup_errors=('CLEANUP_UNCONFIRMED',))
    if fault=='short_input': process=replace(process,stdin_bytes_written=len(request)-1)
    if fault=='malformed_output': process=replace(process,stdout=b'not json')
    result=finalization.finalize_correction_process(request,process,**args)
    assert result['status']==('HELD_RESULT_RECONSTRUCTION' if fault=='malformed_output' else 'HELD_PROCESS_FAILURE')
    stored=json.loads((tmp_path/result['parent_original']['file']).read_bytes())
    assert stored['process']['primary_error']==process.primary_error
    assert not result['campaign_advance_allowed']
