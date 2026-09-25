"""Read-only parent reconstruction. No campaign progression or motor authority."""
import base64

from rocell.application.first_motion_contract import canonical
from rocell.application.physical_onboarding_durability import contained_path,read_bounded_regular_file
from rocell.application.wrist_correction_capture import correction_capture_original
from rocell.application.wrist_correction_result_publication import reconcile_wrist_correction_result
from .wrist_correction_native_protocol import decode_request,validate_payload,digest,require
from .wrist_correction_native_result import load_result_original,decode_outcome
from .wrist_correction_evidence_store import load_evidence
from .owned_worker_process import decode_owned_json


def review_correction_child_result(raw,*,request_raw,assigned_root,authority,
        owned_process_id,process_started_ns,process_finished_ns):
    loaded=load_result_original(raw,request_raw=request_raw,assigned_root=assigned_root,authority=authority,
        owned_process_id=owned_process_id,process_started_ns=process_started_ns,process_finished_ns=process_finished_ns)
    wire=decode_request(request_raw);payload=wire['payload'];request=validate_payload(payload)
    outcome=decode_outcome(loaded['original_bytes'])
    fields={'schema','status','trial','capture_envelopes','errors','publication','lifecycle',
        'owned_process_verified','physical_stop_verified','motion_authorized','replay_allowed'}
    require(set(outcome)==fields and all(outcome[k] is False for k in
        ('owned_process_verified','physical_stop_verified','motion_authorized','replay_allowed')),
        'Exact non-authorizing outcome required')
    result=dict(schema='rocell.wrist_correction_parent_review.v1',status='HELD_INCOMPLETE_RESULT',
        worker_receipt=loaded['worker_receipt'],report=None,reported_endpoint_reconstructed=False,
        process_containment_verified=False,physical_accuracy_verified=False,campaign_advance_allowed=False)
    if outcome['publication'] is None:
        return result
    trial=outcome['trial'];envelopes=outcome['capture_envelopes'];life=outcome['lifecycle']
    final_mode=trial.get('schema')=='rocell.wrist_correction_trial.v2'
    require(type(envelopes) is dict and set(envelopes)==({'baseline','post','final'} if final_mode else {'baseline','post'}),
        'Exact capture originals required')
    for phase in ('baseline','post'):
        projected=correction_capture_original(request,envelopes[phase],phase=phase,
            command_completed_ns=trial['write']['finished_ns'] if phase=='post' else None)
        require(projected==trial[phase],'Collector envelope differs from trial')
    context=request.to_dict();prefix=context['attempt_id']+'-wrist-correction-'
    def read(suffix,maximum):
        return read_bounded_regular_file(contained_path(assigned_root,prefix+suffix+'.json',label='correction result'),maximum_bytes=maximum)
    selection=decode_owned_json(read('owned-selection',65536),maximum=65536)
    final_capture=None
    if final_mode:
        retained=read('final-capture.original',128*1024)
        final=decode_owned_json(retained,maximum=128*1024)
        require(envelopes['final']==dict(final,retention=dict(file=prefix+'final-capture.original.json',
            bytes=len(retained),sha256=digest(retained))), 'Final capture envelope differs from retained original')
        require(trial['final_readback']['owner_pid']==owned_process_id,'Final readback owner differs from process')
        final_capture=final['capture']
    require(all(selection[k]==trial['baseline'][k] for k in ('raw_base64','read_windows','started_ns','finished_ns')),
        'Owned selection baseline changed')
    evidence=load_evidence(payload,assigned_root=assigned_root)
    rebuilt=reconcile_wrist_correction_result(canonical(trial),root=assigned_root,authority=authority,
        bundle=base64.b64decode(selection['review_base64'],validate=True),context=context,
        originals=list(evidence.originals),expected_basis=payload['expected_basis'])
    published=read('result',65536)
    require(published==canonical(rebuilt) and read('trial.original',160*1024)==canonical(trial)
        and outcome['publication']==dict(rebuilt,publication_sha256=digest(published)),
        'Child publication differs from reconstructed originals')
    reservation=decode_owned_json(read('reservation',16384),maximum=16384)
    require(reservation['owner_pid']==owned_process_id,'Command reservation PID differs from process owner')
    lifecycle_fields={'schema','phase','request_sha256','connection_id','owned_handle_count','pending_io_count',
        'read_calls','read_bytes','confirmed_write_bytes','late_cleanup_read_base64','errors','physical_stop_verified'}
    require(type(life) is dict and set(life)==lifecycle_fields
        and life.get('schema')=='rocell.wrist_correction_connection_lifecycle.v1'
        and life.get('request_sha256')==request.request_sha256 and life.get('connection_id')==context['attempt_id']
        and life.get('physical_stop_verified') is False,'Correction lifecycle association mismatch')
    for phase in ('baseline','post'):
        # Final readback uses the same handle and baseline read budget.
        extra_calls=final_capture['read_calls'] if final_mode and phase=='baseline' else 0
        extra_bytes=final_capture['raw']['bytes'] if final_mode and phase=='baseline' else 0
        require(type(life['read_calls'][phase]) is int and type(life['read_bytes'][phase]) is int
            and life['read_calls'][phase]==envelopes[phase]['read_calls']+extra_calls
            and life['read_bytes'][phase]==envelopes[phase]['raw']['bytes']+extra_bytes,'Lifecycle capture counters differ')
    require(type(life['confirmed_write_bytes']) is int and life['confirmed_write_bytes']==trial['write']['confirmed_bytes'],
        'Lifecycle write counter differs')
    require(loaded['worker_receipt']['consumed_ns']<=trial['baseline']['started_ns']
        and trial['cleanup']['finished_ns']<=process_finished_ns,'Trial outside owned process interval')
    status=rebuilt['report']['endpoint']['status']
    require(outcome['status']==status,'Child endpoint label differs from reconstruction')
    clean=(life.get('phase')=='CLOSED' and type(life.get('owned_handle_count')) is int
        and life['owned_handle_count']==0 and type(life.get('pending_io_count')) is int
        and life['pending_io_count']==0 and life.get('errors')==[] and outcome['errors']==[]
        and life['late_cleanup_read_base64']=='' and trial['cleanup']['all_handles_closed'] is True
        and trial['cleanup']['pending_io_count']==0)
    result.update(status=status if clean and loaded['worker_receipt']['finished_within_deadline'] else 'HELD_PROCESS_OR_CLEANUP',
        report=rebuilt['report'],reported_endpoint_reconstructed=True)
    return result
