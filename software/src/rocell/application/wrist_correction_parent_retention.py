"""Retain bounded parent process evidence even without a valid child result.

This records failure, not success. Process termination does not establish motor
stop, and missing child output must never authorize a resend or campaign step.
"""
import base64
from dataclasses import replace
from pathlib import Path
from .first_motion_contract import canonical
from .physical_onboarding_durability import safe_root,contained_path,read_bounded_regular_file,publish_reservation_bytes
from rocell.providers.windows.wrist_correction_native_protocol import decode_request,digest,require,fixed_budget
from rocell.providers.windows.owned_worker_process import OwnedWorkerResult


def _stream(raw,limit):
    require(type(raw) is bytes,'Immutable parent output required')
    kept=raw[:limit]
    return dict(observed_bytes=len(raw),observed_sha256=digest(raw),retained_bytes=len(kept),
        retained_sha256=digest(kept),base64=base64.b64encode(kept).decode('ascii'),truncated=len(kept)!=len(raw))


def retain_correction_parent_result(request_raw,process_result,*,assigned_root):
    """Write one exclusive diagnostic original; callers must hold on failure.

    A process result may have no computed wire hash if admission failed early.
    Both hashes are retained; a mismatch is marked, never silently repaired.
    parsed_result is intentionally omitted: raw stdout is the evidence.
    """
    wire=decode_request(request_raw)
    require(type(process_result) is OwnedWorkerResult,'Exact process-owner result required')
    root=safe_root(assigned_root)
    require(root==Path(wire['payload']['root']),'Assigned correction retention root differs')
    require(process_result.attempt_id==wire['attempt_id'],'Parent process attempt differs')
    require(type(process_result.status) is str and len(process_result.status)<=256
        and (process_result.primary_error is None or type(process_result.primary_error) is str
             and len(process_result.primary_error)<=256)
        and type(process_result.cleanup_errors) is tuple and len(process_result.cleanup_errors)<=258
        and all(type(e) is str and len(e)<=256 for e in process_result.cleanup_errors),
        'Bounded parent diagnostic labels required')
    budget=fixed_budget()
    summary=replace(process_result,parsed_result=None).to_dict()
    prefix=wire['attempt_id']+'-wrist-correction-'
    child_name=prefix+'outcome.original.json'
    child=dict(file=child_name,status='MISSING',semantic_verification_performed=False)
    try:
        child_path=contained_path(root,child_name,label='correction child outcome')
        if child_path.exists():
            original=read_bounded_regular_file(child_path,maximum_bytes=512*1024)
            child.update(status='PRESENT_UNVERIFIED',bytes=len(original),sha256=digest(original))
    except Exception as error:
        child.update(status='UNREADABLE',error_type=type(error).__name__)
    report=dict(schema='rocell.wrist_correction_parent_process_original.v1',
        request=_stream(request_raw,65536),expected_request_sha256=wire['request_sha256'],
        request_hash_matches=process_result.request_sha256==wire['request_sha256'],
        process=summary,stdout=_stream(process_result.stdout,budget.stdout_bytes),
        stderr=_stream(process_result.stderr,budget.stderr_bytes),child_outcome=child,
        physical_stop_verified=False,endpoint_verified=False,campaign_advance_allowed=False,replay_allowed=False)
    original=canonical(report)
    name=prefix+'parent-process.original.json'
    publish_reservation_bytes(root,name,original,maximum_bytes=1024*1024)
    return dict(status='RETAINED',file=name,bytes=len(original),sha256=digest(original),
        endpoint_verified=False,campaign_advance_allowed=False,replay_allowed=False)
