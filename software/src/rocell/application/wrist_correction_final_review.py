"""Reconstruct final-readback review association, without files or device IO."""
import re
from .first_motion_contract import canonical
from .wizard_diagnostic_coordinator import decode_diagnostic_json
from .wrist_correction_final_capture import validate_final_capture
from rocell.providers.windows.wrist_correction_current_context import WristCorrectionContextRequest
from rocell.providers.windows.wrist_correction_native_protocol import digest,require


def final_readback_intent(authority,*,original_bundle,context,originals,samples,basis,
        claim_raw,capture_raw,owned_process_id,now_ns):
    request=WristCorrectionContextRequest(canonical(context))
    original=authority.verify(original_bundle,expected_context=context,originals=originals,
        samples=samples,now_ns=now_ns,expected_basis=basis)
    claim=decode_diagnostic_json(claim_raw,maximum=65536)
    captured=decode_diagnostic_json(capture_raw,maximum=128*1024)
    require(type(claim_raw) is bytes and canonical(claim)==claim_raw
        and type(claim) is dict and set(claim)=={'schema','request_sha256','selection_sha256',
            'connection_id','owner_pid','claimed_ns','record_hashes','motion_authorized'}
        and claim['schema']=='rocell.wrist_correction_final_capture_claim.v1','Exact final capture claim required')
    require(type(owned_process_id) is int and owned_process_id>0 and type(claim['owner_pid']) is int and claim['owner_pid']==owned_process_id
        and claim['request_sha256']==request.request_sha256 and claim['connection_id']==context['attempt_id']
        and claim['motion_authorized'] is False and type(claim['claimed_ns']) is int
        and context['issued_ns']<=claim['claimed_ns']<=now_ns,'Final capture owner/request association differs')
    records=claim['record_hashes']
    require(type(records) is dict and set(records)=={context['attempt_id']+'-wrist-correction-'+suffix+'.json'
        for suffix in ('opening-reservation','open-claim','owned-selection')}
        and all(type(value) is str and re.fullmatch('[a-f0-9]{64}',value) for value in records.values()),
        'Exact original selection record hashes required')
    require(type(capture_raw) is bytes and canonical(captured)==capture_raw and type(captured) is dict
        and set(captured)=={'schema','claim_sha256','capture','validation','status','error_type','motion_authorized'}
        and captured['schema']=='rocell.wrist_correction_owned_final_capture.v1'
        and captured['claim_sha256']==digest(claim_raw) and captured['motion_authorized'] is False
        and captured['status']=='FINAL_CAPTURE_RETAINED_NOT_ADMITTED' and captured['error_type'] is None,
        'Complete associated final capture required')
    envelope=captured['capture'];saved=captured['validation']
    require(type(envelope) is dict and type(saved) is dict and type(saved.get('checked_at_ns')) is int
        and claim['claimed_ns']<=envelope['started_ns']<=saved['checked_at_ns']<=now_ns,
        'Final capture ordering differs')
    args=dict(basis=basis,baseline_samples=samples,selection_sha256=claim['selection_sha256'])
    current=validate_final_capture(request,envelope,originals,now_ns=now_ns,**args)
    # Reconstruct raw frames, selection, stability and command exactly once per
    # verification. Only checked_at/host_age vary with the verification time.
    # A valid earlier check must follow actual completion; current freshness
    # implies freshness at that earlier time. No result is cached across calls.
    saved_time=saved['checked_at_ns']
    require(max(envelope['finished_ns'],envelope.get('observation_end_ns',envelope['window_deadline_ns']))<=saved_time,
        'Retained final validation precedes capture completion')
    rebuilt=dict(current,checked_at_ns=saved_time,
        host_age_ns=saved_time-current['final_last_received_ns'])
    require(canonical(rebuilt)==canonical(saved),'Retained final readback summary differs from raw evidence')
    require(current['candidate_command']==original['candidate_command']
        and current['nominal_endpoint_rad']==original['nominal_endpoint_rad'],'Final readback changes original command')
    return dict(schema='rocell.wrist_correction_final_review_intent.v1',request_sha256=request.request_sha256,
        original_bundle_sha256=digest(original_bundle),claim_sha256=digest(claim_raw),capture_sha256=digest(capture_raw),
        owner_pid=owned_process_id,connection_id=context['attempt_id'],deadline_ns=context['deadline_ns'],
        last_received_ns=current['final_last_received_ns'],selection_sha256=claim['selection_sha256'],
        candidate_command=current['candidate_command'],nominal_endpoint_rad=current['nominal_endpoint_rad'])
