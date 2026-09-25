"""Recompute completed trial evidence; never authenticate a child or physical motion.

Malformed and failed trials remain available through immutable raw retention.
This separate review accepts only the complete trial form for metric comparison.
Parent process ownership/receipt and independent physical observation still must
be verified separately before any live commissioning decision.
"""
import hashlib

from rocell.arm.first_motion_analysis import analyze_first_motion
from rocell.arm.protocol import encode_line
from .first_motion_contract import FirstMotionRequest, canonical
from .first_motion_capture_validation import validate_clean_first_motion_capture
from .wizard_diagnostic_coordinator import decode_diagnostic_json


def review_completed_first_motion_trial(request, raw, *, expected_basis):
    if (type(request) is not FirstMotionRequest or type(raw) is not bytes
            or len(raw)>256*1024
            or expected_basis not in {'SYNTHETIC_WIRE_REHEARSAL','RETAINED_PHYSICAL_CAPTURE'}):
        raise ValueError('Bounded exact commissioning trial and evidence basis required')
    trial=decode_diagnostic_json(raw,maximum=256*1024)
    fields={'schema','basis','request_sha256','status','baseline','post','write','analysis',
            'cleanup','errors','physical_movement_verified','physical_stop_verified',
            'campaign_advance_allowed','replay_allowed'}
    if (type(trial) is not dict or set(trial)!=fields
            or trial['schema']!='rocell.owned_first_motion_trial.v1'
            or trial['request_sha256']!=request.request_sha256 or trial['basis']!=expected_basis
            or trial['errors']!=[] or any(trial[k] is not False for k in
                ('physical_movement_verified','physical_stop_verified','campaign_advance_allowed','replay_allowed'))):
        raise ValueError('Exact complete diagnostic-only trial required')
    write=trial['write']
    if (type(write) is not dict or set(write)!={'write_attempted','write_started_ns',
            'write_finished_ns','confirmed_write_bytes','write_completion_uncertain'}
            or write['write_attempted'] is not True or write['write_completion_uncertain'] is not False
            or type(write['confirmed_write_bytes']) is not int
            or write['confirmed_write_bytes']!=len(encode_line(request.to_dict()['command']))):
        raise ValueError('Full exact write receipt required')
    start,finish=write['write_started_ns'],write['write_finished_ns']
    if (type(start) is not int or type(finish) is not int or not 0<=finish-start<=1_000_000_000):
        raise ValueError('Write timing invalid')
    before,after=trial['baseline'],trial['post']
    baseline_raw=validate_clean_first_motion_capture(request,before,phase='baseline')
    post_raw=validate_clean_first_motion_capture(request,after,phase='post',command_completed_ns=finish)
    analysis=analyze_first_motion(request,baseline_raw,before['read_windows'],post_raw,after['read_windows'],
        baseline_started_ns=before['started_ns'],baseline_finished_ns=before['finished_ns'],
        write_started_ns=start,write_finished_ns=finish,observation_end_ns=after['finished_ns'],basis=expected_basis)
    if canonical(analysis)!=canonical(trial['analysis']) or trial['status']!=analysis['status']:
        raise ValueError('Child analysis/status differs from raw recomputation')
    cleanup=trial['cleanup']
    if (type(cleanup) is not dict or set(cleanup)!={'status','started_ns','finished_ns','all_handles_closed','pending_io_count'}
            or cleanup['status']!='HANDLES_CLOSED' or cleanup['all_handles_closed'] is not True
            or type(cleanup['pending_io_count']) is not int or cleanup['pending_io_count']!=0):
        raise ValueError('Complete cleanup receipt required')
    cs,cf=cleanup['started_ns'],cleanup['finished_ns']
    if (type(cs) is not int or type(cf) is not int
            or not after['finished_ns']<=cs<=cf<=request.to_dict()['deadline_monotonic_ns']
            or cf-cs>2_000_000_000):
        raise ValueError('Cleanup timing invalid')
    return dict(schema='rocell.first_motion_completed_trial_review.v1',
        request_sha256=request.request_sha256,original_sha256=hashlib.sha256(raw).hexdigest(),
        status='TRIAL_DATA_CONSISTENT_NOT_PHYSICALLY_QUALIFIED',analysis=analysis,
        owned_process_receipt_verified=False,physical_movement_verified=False,
        physical_stop_verified=False,campaign_advance_allowed=False,replay_allowed=False)
