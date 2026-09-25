"""Internal single-trial composition; no public/native launch registration.

Caller must own a contained process and exact admitted connection. Cleanup is
always attempted; uncertain writes never cause a resend, home or return move.
"""
import base64
import hashlib
from threading import Event

from rocell.providers.windows.wrist_correction_serial_connection import WristCorrectionSerialConnection
from rocell.safety.wrist_correction_admission import WristCorrectionPermit
from .wrist_correction_capture import capture_wrist_correction_window, correction_capture_original
from .wrist_correction_result_publication import publish_wrist_correction_result
from .wrist_correction_owned_final_capture import retain_owned_final_capture
from .physical_onboarding_durability import contained_path,read_bounded_regular_file,publish_reservation_bytes
from .wizard_diagnostic_coordinator import decode_diagnostic_json
from .first_motion_contract import canonical


def _run_wrist_correction_trial(connection,permit,*,cancellation,clock_ns,idle_wait=None):
    if (type(connection) is not WristCorrectionSerialConnection or type(permit) is not WristCorrectionPermit
            or not connection._api.matches_authorization(connection._request,permit)
            or type(cancellation) is not Event or cancellation is not permit._binding._cancel
            or not callable(clock_ns) or (idle_wait is not None and not callable(idle_wait))):
        raise ValueError('Exact owned correction trial dependencies required')
    request=connection._request;binding=permit._binding;reader=binding._reader
    trial=dict(schema='rocell.wrist_correction_trial.v2',basis=reader._basis,
               baseline=None,post=None,write=None,cleanup=None,final_readback=None)
    result=dict(schema='rocell.owned_wrist_correction_trial.v1',status='NOT_SENT',trial=trial,
        capture_envelopes={},errors=[],publication=None,lifecycle=None,
        owned_process_verified=False,physical_stop_verified=False,motion_authorized=False,replay_allowed=False)
    last=0
    interruption=None
    def now():
        nonlocal last
        value=clock_ns()
        if type(value) is not int or not 0<value<2**63 or value<last:
            raise ValueError('Correction trial clock invalid')
        last=value;return value
    try:
        request.require_start_time(now())
        if cancellation.is_set():
            result['status']='CANCELLED_BEFORE_OPEN'
        else:
            connection.open()
            baseline=capture_wrist_correction_window(request,'baseline',read_once=connection.read,
                cancellation=cancellation,clock_ns=now,idle_wait=idle_wait)
            result['capture_envelopes']['baseline']=baseline
            original=trial['baseline']=correction_capture_original(request,baseline,phase='baseline')
            permit.bind_owned_baseline(request,connection._api.connection_id,binding._port,
                base64.b64decode(original['raw_base64'],validate=True),original['read_windows'],
                started_ns=original['started_ns'],finished_ns=original['finished_ns'])
            if cancellation.is_set():
                result['status']='CANCELLED_BEFORE_WRITE'
            else:
                # Preparation can outlive the original sample's dispatch age.
                # Obtain a separate, retained readback; never relabel old data.
                final=retain_owned_final_capture(connection,permit,idle_wait=idle_wait)
                result['capture_envelopes']['final']=final
                permit.prepare_final_dispatch(connection)
                scope=binding._final_scope
                trial['final_readback']=dict(review_sha256=hashlib.sha256(scope._review).hexdigest(),
                    claim_sha256=hashlib.sha256(scope._args['claim_raw']).hexdigest(),
                    capture_sha256=hashlib.sha256(scope._args['capture_raw']).hexdigest(),owner_pid=scope._pid)
                payload=permit.selected_payload()
                write=trial['write']=dict(payload_base64=base64.b64encode(payload).decode(),started_ns=now(),
                    finished_ns=None,confirmed_bytes=0,completion_uncertain=True,dispatch_checked_ns=None)
                try:
                    count=connection.write_once(payload)
                    write['finished_ns']=now()
                    if type(count) is int and 0<=count<=len(payload): write['confirmed_bytes']=count
                    write['completion_uncertain']=(type(count) is not int or count!=len(payload)
                        or write['finished_ns']-write['started_ns']>1_000_000_000)
                except Exception as error:
                    result['errors'].append(type(error).__name__);write['finished_ns']=now()
                write['dispatch_checked_ns']=getattr(binding,'_final_dispatch_checked_ns',None)
                result['status']='WRITE_UNCERTAIN_NO_RETRY' if write['completion_uncertain'] else 'CAPTURED'
                post=capture_wrist_correction_window(request,'post',read_once=connection.read,
                    cancellation=cancellation,clock_ns=now,idle_wait=idle_wait,command_completed_ns=write['finished_ns'])
                result['capture_envelopes']['post']=post
                trial['post']=correction_capture_original(request,post,phase='post',command_completed_ns=write['finished_ns'])
    except BaseException as error:
        result['errors'].append(type(error).__name__)
        result['status']='HELD_AFTER_WRITE_ATTEMPT' if trial['write'] else 'HELD_BEFORE_WRITE'
        if not isinstance(error,Exception):
            interruption=error
            result['status']='INTERRUPTED_AFTER_WRITE_ATTEMPT' if trial['write'] else 'INTERRUPTED_BEFORE_WRITE'
    finally:
        permit.revoke()
        try:
            cleanup=connection.close(2000)
            trial['cleanup']=dict(finished_ns=now(),all_handles_closed=cleanup.all_handles_closed,
                                  pending_io_count=cleanup.pending_io_count)
        except Exception as error:
            result['errors'].append(type(error).__name__);result['status']='CLEANUP_UNCONFIRMED'
        result['lifecycle']=connection.snapshot()
    if interruption is None and all(trial[k] is not None for k in ('baseline','post','write','cleanup')):
        try:
            selection=decode_diagnostic_json(read_bounded_regular_file(contained_path(binding._root,
                request.to_dict()['attempt_id']+'-wrist-correction-owned-selection.json',label='owned selection'),
                maximum_bytes=65536),maximum=65536)
            result['publication']=publish_wrist_correction_result(canonical(trial),root=binding._root,
                authority=reader._authority,bundle=base64.b64decode(selection['review_base64'],validate=True),
                context=request.to_dict(),originals=reader._originals,expected_basis=reader._basis)
            result['status']=result['publication']['report']['endpoint']['status']
        except Exception as error:
            result['errors'].append(type(error).__name__);result['status']='RESULT_REVIEW_HELD'
    # Retain partial envelopes and cleanup for failures too, before returning
    # or propagating an interrupt. Exclusive publication never replaces an
    # earlier outcome. The outer process supervisor must handle hard kills.
    try:
        raw=canonical(result)
        name=request.to_dict()['attempt_id']+'-wrist-correction-outcome.original.json'
        publish_reservation_bytes(binding._root,name,raw,maximum_bytes=512*1024)
        result['outcome_retention']=dict(status='RETAINED',file=name,bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
    except Exception as error:
        result['outcome_retention']=dict(status='FAILED',error=type(error).__name__)
        result['unretained_trial_status']=result['status']
        result['status']='OUTCOME_RETENTION_FAILED'
    if interruption is not None:
        raise interruption
    return result
