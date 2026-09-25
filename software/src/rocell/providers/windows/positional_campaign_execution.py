"""Finite native-layer campaign runner, not registered for live application use.

Requires an already admitted, unopened owned connection. The parent must still
pin the runtime, supervise a bounded child and qualify physical release. The
runner shares capture/endpoint verification with simulation but leaves final
submission ownership to the native facade. It never retries or returns home.
"""
from threading import Event
import time

from rocell.application.positional_campaign_capture import capture_campaign_window, validate_campaign_capture
from rocell.safety.positional_campaign_admission import PositionalCampaignAdmission, BaselineAgeExceeded
from rocell.arm.campaign_stream_sync import CampaignFramingError
from rocell.safety.positional_campaign_authority import PositionalCampaignIntent
from .positional_campaign_serial_connection import PositionalCampaignSerialConnection


def run_native_campaign(request, admission, connection, *, cancellation,
        clock_ns=time.monotonic_ns, idle_wait=None):
    if (type(request) is not PositionalCampaignIntent
            or type(admission) is not PositionalCampaignAdmission
            or type(connection) is not PositionalCampaignSerialConnection
            or admission.request != request or connection._request != request
            or connection._api._permit is not admission
            or type(cancellation) is not Event or connection._api._cancellation is not cancellation
            or not callable(clock_ns) or (idle_wait is not None and not callable(idle_wait))
            or connection.snapshot()['phase'] != 'UNOPENED'):
        raise ValueError('Exact unopened native campaign composition required')
    result = dict(schema='rocell.native_positional_campaign_trial.v1',
        basis='NATIVE_PATH_UNQUALIFIED', intent_sha256=request.sha256, status='HELD',
        legs=[], errors=[], cleanup=None, lifecycle=None, native_submission_attempts=0,
        native_execution_released=False, physical_movement_verified=False,
        physical_stop_verified=False, replay_allowed=False)
    previous = 0
    stage = 'open'
    def now():
        nonlocal previous
        value = clock_ns()
        if type(value) is not int or not previous <= value < 2**63 or value <= 0:
            raise ValueError('Invalid native campaign clock')
        previous = value
        return value
    def cancelled():
        if cancellation.is_set():
            result['status'] = 'CANCELLED'
            return True
        return False
    def capture(phase, completed=None):
        return capture_campaign_window(request, phase, read_once=connection.read,
            cancellation=cancellation, clock_ns=now, idle_wait=idle_wait,
            command_completed_ns=completed)
    try:
        if not cancelled():
            request.require_start_time(now())
            connection.open()
            for leg in request.to_dict()['legs']:
                if cancelled(): break
                stage = 'begin_leg'
                connection.begin_leg(leg['leg_id'])
                record = dict(leg_id=leg['leg_id'], baseline=None, write=None, post=None, verification=None)
                result['legs'].append(record)
                stage = 'baseline'
                baseline = record['baseline'] = capture('baseline')
                if cancelled(): break
                raw = validate_campaign_capture(request, baseline, phase='baseline')
                admission.bind_baseline(raw, baseline['read_windows'],
                    started_ns=baseline['started_ns'], finished_ns=baseline['finished_ns'])
                stage = 'reserve'
                payload = admission.consume_command()
                if cancelled(): break
                stage = 'write'
                write = record['write'] = dict(started_ns=now(), finished_ns=None,
                    confirmed_bytes=0, uncertain=True)
                count = connection.write_once(payload)
                write['finished_ns'] = now()
                write['confirmed_bytes'] = count
                write['uncertain'] = (count != len(payload)
                    or write['finished_ns'] - write['started_ns'] > 1_000_000_000)
                stage = 'post'
                post = record['post'] = capture('post', write['finished_ns'])
                if cancelled(): break
                raw = validate_campaign_capture(request, post, phase='post',
                    command_completed_ns=write['finished_ns'])
                stage = 'verify'
                verification = record['verification'] = admission.commit_endpoint(raw, post['read_windows'],
                    started_ns=post['started_ns'], finished_ns=post['finished_ns'],
                    confirmed_write_bytes=count, write_finished_ns=write['finished_ns'],
                    write_uncertain=write['uncertain'],write_started_ns=write['started_ns'])
                if cancelled() or verification['state'] == 'HELD': break
            else:
                result['status'] = 'REPORTED_CAMPAIGN_COMPLETE'
    except Exception as error:
        diagnostic=dict(stage=stage,code=type(error).__name__)
        if type(error) is BaselineAgeExceeded:
            diagnostic['timing']=dict(error.diagnostic)
        if type(error) is CampaignFramingError:
            diagnostic['reason']=error.reason
        result['errors'].append(diagnostic)
        result['status'] = 'CANCELLED' if cancellation.is_set() else 'HELD'
    finally:
        try:
            admission.revoke()
        finally:
            # Cleanup must run even when the lifecycle clock is broken.
            started = None
            try:
                started = now()
            except Exception as error:
                result['errors'].append(dict(stage='cleanup_clock', code=type(error).__name__))
            try:
                cleanup = connection.close(2000)
                finished = now()
                within_budget = (started is not None and finished-started <= 2_000_000_000
                    and finished <= request.to_dict()['deadline_ns'])
                result['cleanup'] = dict(all_handles_closed=cleanup.all_handles_closed,
                    pending_io_count=cleanup.pending_io_count, within_budget=within_budget,
                    started_ns=started, finished_ns=finished)
                if not cleanup.all_handles_closed or cleanup.pending_io_count or not within_budget:
                    result['status'] = 'CLEANUP_UNCONFIRMED'
            except Exception as error:
                result['errors'].append(dict(stage='cleanup', code=type(error).__name__))
                result['status'] = 'CLEANUP_UNCONFIRMED'
            result['lifecycle'] = connection.snapshot()
            result['native_submission_attempts'] = len(connection._api._campaign_tokens)
    result['skipped_leg_ids'] = [leg['leg_id'] for leg in request.to_dict()['legs'][len(result['legs']):]]
    return result
