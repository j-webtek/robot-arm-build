"""Reconstruct a completed observational trial from bounded original bytes.

This verifies data consistency, not the worker process, physical movement or an
operator observation. Failure originals must remain available for diagnostics.
"""
import hashlib

from rocell.arm.observational_wrist_analysis import preview_from_capture, assess_observational_response
from rocell.arm.protocol import encode_line
from rocell.safety.observational_review_authority import ObservationalIntent
from .first_motion_contract import canonical
from .observational_command_binding import MAX_SELECTED_BASELINE_AGE_NS
from .observational_capture import validate_clean_observational_capture
from .wizard_diagnostic_coordinator import decode_diagnostic_json


def review_completed_observational_trial(request, trial_raw, selection_raw, *, expected_basis):
    if (type(request) is not ObservationalIntent or type(trial_raw) is not bytes
            or type(selection_raw) is not bytes
            or expected_basis not in ('SYNTHETIC_WIRE_REHEARSAL', 'RETAINED_PHYSICAL_CAPTURE')):
        raise ValueError('Typed intent and bounded original result bytes required')
    trial = decode_diagnostic_json(trial_raw, maximum=256*1024)
    selection = decode_diagnostic_json(selection_raw, maximum=16384)
    fields = {'schema','basis','request_sha256','status','baseline','post','selection',
              'write','cleanup','errors','physical_movement_verified','physical_stop_verified',
              'campaign_advance_allowed','replay_allowed'}
    if (type(trial) is not dict or set(trial) != fields or canonical(trial) != trial_raw
            or trial['schema'] != 'rocell.owned_observational_trial.v1'
            or trial['request_sha256'] != request.request_sha256
            or trial['basis'] != expected_basis or trial['status'] != 'AWAITING_OPERATOR_OBSERVATION'
            or trial['errors'] != [] or any(trial[name] is not False for name in
                ('physical_movement_verified','physical_stop_verified','campaign_advance_allowed','replay_allowed'))):
        raise ValueError('Clean completed observational trial required; failures remain diagnostics')
    body = request.to_dict()
    selection_fields = {'schema','session_id','attempt_id','connection_id','usb_identity',
                        'preview','selected_ns','physical_authority'}
    if (type(selection) is not dict or set(selection) != selection_fields
            or canonical(selection) != selection_raw
            or selection['schema'] != 'rocell.observational_command_selection.v1'
            or selection['session_id'] != body['session_id'] or selection['attempt_id'] != body['attempt_id']
            or selection['connection_id'] != body['attempt_id']
            or canonical(selection['usb_identity']) != canonical(body['usb_identity'])
            or selection['physical_authority'] is not False):
        raise ValueError('Exact owned selection original required')
    baseline, post, write, cleanup = (trial[name] for name in ('baseline','post','write','cleanup'))
    if (type(write) is not dict or set(write) != {'write_started_ns','write_finished_ns',
            'write_attempted','confirmed_write_bytes','write_completion_uncertain'}
            or write['write_attempted'] is not True or write['write_completion_uncertain'] is not False):
        raise ValueError('Exact completed write accounting required')
    before = validate_clean_observational_capture(request, baseline, phase='baseline')
    after = validate_clean_observational_capture(request, post, phase='post',
        command_completed_ns=write['write_finished_ns'])
    times = [baseline['finished_ns'], selection['selected_ns'], write['write_started_ns'],
             write['write_finished_ns'], post['started_ns']]
    if (any(type(t) is not int for t in times) or times != sorted(times)
            or times[1]-times[0] > 100_000_000 or times[3]-times[2] > 1_000_000_000):
        raise ValueError('Selection/write timing mismatch')
    preview = preview_from_capture(before, baseline['read_windows'],
        started_ns=baseline['started_ns'], finished_ns=baseline['finished_ns'],
        now_ns=selection['selected_ns'], direction=body['direction'], policy=body['policy'])
    if (canonical(preview) != canonical(selection['preview'])
            or canonical(trial['selection']) != canonical(dict(preview=preview,
                selection_sha256=hashlib.sha256(selection_raw).hexdigest(), motion_authorized=False))
            or type(write['confirmed_write_bytes']) is not int
            or write['confirmed_write_bytes'] != len(encode_line(preview['candidate_command']))
            or write['write_started_ns']-preview['baseline_last_host_received_ns'] > MAX_SELECTED_BASELINE_AGE_NS):
        raise ValueError('Derived command, selection or byte accounting mismatch')
    if (type(cleanup) is not dict or set(cleanup) != {'status','started_ns','finished_ns',
            'all_handles_closed','pending_io_count'} or cleanup['status'] != 'HANDLES_CLOSED'
            or cleanup['all_handles_closed'] is not True or type(cleanup['pending_io_count']) is not int
            or cleanup['pending_io_count'] != 0
            or any(type(cleanup[k]) is not int for k in ('started_ns','finished_ns'))
            or not post['finished_ns'] <= cleanup['started_ns'] <= cleanup['finished_ns'] <= body['deadline_ns']
            or cleanup['finished_ns']-cleanup['started_ns'] > 2_000_000_000):
        raise ValueError('Clean bounded cleanup accounting required')
    analysis = assess_observational_response(before, baseline['read_windows'], after, post['read_windows'],
        baseline_started_ns=baseline['started_ns'], baseline_finished_ns=baseline['finished_ns'],
        write_started_ns=write['write_started_ns'], write_finished_ns=write['write_finished_ns'],
        observation_end_ns=post['finished_ns'], direction=body['direction'], policy=body['policy'],
        actual_command=preview['candidate_command'], operator_outcome='UNKNOWN',
        operator_covered_trial=False, transport_clean=True, basis=expected_basis)
    return dict(schema='rocell.observational_result_review.v1',
        status='TRIAL_DATA_CONSISTENT_AWAITING_OBSERVATION',
        trial_sha256=hashlib.sha256(trial_raw).hexdigest(),
        selection_sha256=hashlib.sha256(selection_raw).hexdigest(),
        request_sha256=request.request_sha256, analysis=analysis,
        owned_process_verified=False, physical_movement_verified=False,
        campaign_advance_allowed=False, motion_authorized=False)
