"""Finite campaign on an already-owned test connection, with unconditional cleanup.

Native composition is not released. This integration entry currently requires
synthetic provenance and is exercised by incapable test adapters. A future native
parent must enforce callback IO/process deadlines and exact dispatch tokens;
Python alone cannot preempt a blocked callback or physically stop a servo.
"""
from threading import Event
import time

from rocell.safety.positional_campaign_authority import PositionalCampaignIntent
from rocell.safety.positional_campaign_admission import PositionalCampaignAdmission
from .positional_campaign_capture import capture_campaign_window,validate_campaign_capture
from .endpoint_owned_trial import EndpointCleanupResult


def run_owned_positional_campaign(request,admission,*,read_once,write_once,close_once,
        cancellation,basis,clock_ns=time.monotonic_ns,idle_wait=None):
    if (type(request) is not PositionalCampaignIntent or type(admission) is not PositionalCampaignAdmission
            or admission.request!=request or basis!='SYNTHETIC_WIRE_REHEARSAL'
            or type(cancellation) is not Event or not all(callable(fn) for fn in (read_once,write_once,close_once,clock_ns))
            or (idle_wait is not None and not callable(idle_wait))):
        raise ValueError('Exact incapable owned-campaign dependencies required')
    result=dict(schema='rocell.owned_positional_campaign.v1',basis=basis,status='HELD',
        intent_sha256=request.sha256,legs=[],errors=[],cleanup=None,
        simulated_write_attempts=0,physical_write_count=0,native_execution_released=False,
        physical_stop_verified=False,replay_allowed=False)
    previous=0
    def now():
        nonlocal previous
        value=clock_ns()
        if type(value) is not int or not 0<value<2**63 or value<previous:
            raise ValueError('Invalid campaign clock')
        previous=value
        return value
    try:
        for leg in request.to_dict()['legs']:
            if cancellation.is_set():
                result['status']='CANCELLED'
                break
            # Do not spend the reserved cleanup tail starting another leg.
            # Checked before any baseline IO; later dispatch checks remain
            # necessary because reads and durable claims can consume time.
            request.require_remaining_time(now(), phase='leg')
            record=dict(leg_id=leg['leg_id'],baseline=None,write=None,post=None,verification=None)
            result['legs'].append(record)
            baseline=record['baseline']=capture_campaign_window(request,'baseline',read_once=read_once,
                cancellation=cancellation,clock_ns=now,idle_wait=idle_wait)
            raw=validate_campaign_capture(request,baseline,phase='baseline')
            admission.bind_baseline(raw,baseline['read_windows'],started_ns=baseline['started_ns'],finished_ns=baseline['finished_ns'])
            if cancellation.is_set():
                result['status']='CANCELLED'
                break
            payload=admission.consume_command()
            # Consumption may perform storage/context IO. A cancellation arriving
            # there consumes the claim but still withholds the actual submission.
            if cancellation.is_set():
                result['status']='CANCELLED'
                break
            dispatch_ns=now()
            admission.check_dispatch_time(dispatch_ns)
            # Cancellation can arrive during the clock/admission check, after
            # the earlier check. Keep the consumed claim but withhold this write.
            # This is not a physical stop for a command already submitted.
            if cancellation.is_set():
                result['status']='CANCELLED'
                break
            dispatch_ns=now()
            admission.claim_submission(payload, dispatch_ns)
            if cancellation.is_set():
                result['status']='CANCELLED'
                break
            write=record['write']=dict(started_ns=dispatch_ns,finished_ns=None,confirmed_bytes=0,uncertain=True)
            result['simulated_write_attempts']+=1
            try:
                count=write_once(payload)
                write['finished_ns']=now()
                if type(count) is int and 0<=count<=len(payload): write['confirmed_bytes']=count
                write['uncertain']=(type(count) is not int or count!=len(payload)
                    or write['finished_ns']-write['started_ns']>1_000_000_000)
            except Exception as error:
                result['errors'].append(type(error).__name__)
                write['finished_ns']=now()
            # Retain evidence even when a submission may have partly succeeded.
            post=record['post']=capture_campaign_window(request,'post',read_once=read_once,
                cancellation=cancellation,clock_ns=now,idle_wait=idle_wait,command_completed_ns=write['finished_ns'])
            raw=validate_campaign_capture(request,post,phase='post',command_completed_ns=write['finished_ns'])
            verification=record['verification']=admission.commit_endpoint(raw,post['read_windows'],
                started_ns=post['started_ns'],finished_ns=post['finished_ns'],
                confirmed_write_bytes=write['confirmed_bytes'],write_finished_ns=write['finished_ns'],write_uncertain=write['uncertain'],write_started_ns=write['started_ns'])
            if cancellation.is_set():
                result['status']='CANCELLED'
                break
            if verification['state']=='HELD': break
        else:
            result['status']='SIMULATION_COMPLETE'
    except Exception as error:
        result['errors'].append(type(error).__name__)
        result['status']='CANCELLED' if cancellation.is_set() else 'HELD'
    finally:
        admission.revoke()
        started=None
        try:
            started=now()
        except Exception as error:
            result['errors'].append(type(error).__name__)
        try:
            cleanup=close_once(2000)
            finished=now()
            clean=(type(cleanup) is EndpointCleanupResult and cleanup.all_handles_closed is True
                and type(cleanup.pending_io_count) is int and cleanup.pending_io_count==0
                and started is not None and finished-started<=2_000_000_000
                and finished<=request.to_dict()['deadline_ns'])
            result['cleanup']=dict(status='HANDLES_CLOSED' if clean else 'CLEANUP_UNCERTAIN',
                started_ns=started,finished_ns=finished)
        except Exception as error:
            result['errors'].append(type(error).__name__)
            clean=False
            result['cleanup']=dict(status='CLEANUP_UNCERTAIN')
        if not clean: result['status']='CLEANUP_UNCERTAIN'
    result['skipped_leg_ids']=[leg['leg_id'] for leg in request.to_dict()['legs'][len(result['legs']):]]
    if (result['status'] in ('SIMULATION_COMPLETE','HELD') and result['legs']
            and all(leg['verification'] is not None for leg in result['legs'])):
        from .positional_campaign_reconstruction import verify_completed_owned_campaign
        try:
            result['reconstruction']=verify_completed_owned_campaign(request,result)
        except Exception as error:
            result['errors'].append(type(error).__name__)
            result['status']='RECONSTRUCTION_FAILED'
    return result
