"""Retain then reconstruct a correction process result, never authorize motion.

The process owner must supply this result and its observed start bound. Raw
failure evidence is saved before any semantic review can raise an exception.
"""
from .first_motion_contract import canonical
from .wrist_correction_parent_retention import retain_correction_parent_result
from .physical_onboarding_durability import publish_reservation_bytes
from rocell.providers.windows.wrist_correction_parent_review import review_correction_child_result
from rocell.providers.windows.wrist_correction_native_protocol import decode_request,digest,require
from rocell.providers.windows.owned_worker_process import OwnedWorkerResult


def finalize_correction_process(request_raw,process_result,*,assigned_root,authority,process_started_ns):
    require(type(process_result) is OwnedWorkerResult,'Exact process-owner result required')
    wire=decode_request(request_raw)
    retention=retain_correction_parent_result(request_raw,process_result,assigned_root=assigned_root)
    result=dict(schema='rocell.wrist_correction_process_finalization.v1',status='HELD_PROCESS_FAILURE',
        process_status=process_result.status,primary_error=process_result.primary_error,
        cleanup_errors=list(process_result.cleanup_errors),parent_original=retention,review=None,
        review_error=None,physical_accuracy_verified=False,physical_stop_verified=False,
        campaign_advance_allowed=False,replay_allowed=False)
    # A zero exit alone is insufficient. Missing/partial input or unresolved
    # process cleanup prevents semantic success regardless of stdout contents.
    clean=(process_result.status=='SUCCEEDED' and process_result.primary_error is None
        and process_result.cleanup_errors==() and process_result.process_created is True
        and process_result.initial_thread_resumed is True and process_result.tree_exit_confirmed is True
        and type(process_result.returncode) is int and process_result.returncode==0
        and process_result.request_sha256==wire['request_sha256']
        and type(process_result.stdin_bytes_written) is int and process_result.stdin_bytes_written==len(request_raw))
    if clean:
        try:
            result['review']=review_correction_child_result(process_result.stdout,request_raw=request_raw,
                assigned_root=assigned_root,authority=authority,owned_process_id=process_result.owned_process_id,
                process_started_ns=process_started_ns,process_finished_ns=process_result.finished_monotonic_ns)
            result['status']=result['review']['status']
        except Exception as error:
            result['status']='HELD_RESULT_RECONSTRUCTION'
            result['review_error']=type(error).__name__
    original=canonical(result)
    name=wire['attempt_id']+'-wrist-correction-parent-verdict.original.json'
    publish_reservation_bytes(assigned_root,name,original,maximum_bytes=256*1024)
    result['verdict_retention']=dict(file=name,bytes=len(original),sha256=digest(original))
    return result
