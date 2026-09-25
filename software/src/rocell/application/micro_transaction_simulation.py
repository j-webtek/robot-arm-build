"""Offline transaction composition. There is deliberately no injected sender.

Consumes a staged intent and evaluates synthetic raw feedback and hold traces.
Only report export is injected. Virtual times/faults are scenario inputs, never
hardware observations. A future native adapter requires separate review.
"""
from copy import deepcopy
from rocell.application.first_motion_contract import canonical

from rocell.application.micro_endpoint_review import review_micro_feedback, JOINTS
from rocell.providers.windows.arm_wifi_observation import review_observation
from rocell.providers.windows.arm_wifi_feedback import MAC


def run_simulated_transaction(admission, *, now_ns, consume_elapsed_ns=0,
                              receipt_latency_ns=50_000_000, samples=(), hold=None,
                              send_fault=False, cancelled=False, control_session=None, export):
    """One virtual send maximum; no retry, return, or hold after endpoint failure.

    Input sample times must be absolute virtual host times. A receipt is not
    feedback. Export receives a detached report on every completed code path;
    export failure returns a failure report in memory without claiming storage.
    """
    result=dict(schema='rocell.micro_transaction_simulation.v1',simulation_only=True,
        motion_authorized=False,native_sends=0,simulated_send_attempts=0,
        status='STOPPED',phase='ADMISSION',samples=[],hold=None,
        automatic_retry_allowed=False,automatic_next_command_allowed=False,
        export_succeeded=False)
    try:
        if (any(type(t) is not int for t in (now_ns,consume_elapsed_ns,receipt_latency_ns))
                or consume_elapsed_ns<0 or receipt_latency_ns<0
                or type(send_fault) is not bool or type(cancelled) is not bool):
            raise ValueError('Explicit virtual timing and faults required')
        context=admission.snapshot()
        result['context']=context
        result['consumption']=admission.consume(context['command'],now_ns=now_ns,
                                               observed_mac=MAC,cancelled=cancelled)
        result['phase']='SEND_BOUNDARY'
        dispatch=now_ns+consume_elapsed_ns
        # Replay and durable writes can use up the baseline freshness window.
        if not context['created_ns']<=dispatch<=context['expires_ns']:
            result['reason']='EXPIRED_BEFORE_SEND'
        else:
            if control_session is not None:
                from rocell.safety.micro_control_session import MicroControlSession
                if type(control_session) is not MicroControlSession:
                    raise ValueError('Exact cooperative session required')
                boundary=control_session.claim_staged_boundary(canonical(context['command']),cancelled=cancelled)
                if boundary['claimed_ns']!=dispatch:
                    raise ValueError('Virtual boundary clock mismatch')
                result['cooperative_boundary']=boundary
            result.update(simulated_send_attempts=1,dispatch_ns=dispatch,phase='RECEIPT')
            receipt=dispatch+receipt_latency_ns
            result['receipt_ns']=receipt
            if send_fault or receipt_latency_ns>800_000_000:
                result['reason']='COMMAND_OUTCOME_UNCERTAIN'
            else:
                result['phase']='ENDPOINT'
                result['samples']=deepcopy(list(samples))
                evaluated=receipt
                verdict=None
                for index,sample in enumerate(result['samples']):
                    evaluated=max(evaluated,round(sample.get('response_finished_monotonic_s',receipt/1e9)*1e9))
                    verdict=review_micro_feedback(result['samples'][:index+1],
                        baseline=[context['baseline']['joints_rad'][j] for j in JOINTS],
                        dispatch_ns=dispatch,receipt_ns=receipt,evaluated_ns=evaluated)
                    if verdict['status'] not in ('NOT_YET_SETTLED','REPORTED_SETTLED'):
                        break
                if verdict is None or verdict['status']=='NOT_YET_SETTLED':
                    verdict=review_micro_feedback(result['samples'],
                        baseline=[context['baseline']['joints_rad'][j] for j in JOINTS],
                        dispatch_ns=dispatch,receipt_ns=receipt,
                        evaluated_ns=max(evaluated,dispatch+10_000_000_000))
                result['endpoint']=verdict
                if not verdict['reported_settled']:
                    result['reason']=verdict['status']
                else:
                    result['phase']='HOLD'
                    result['hold']=deepcopy(hold)
                    if hold is None or hold.get('status')!='SUCCEEDED':
                        result['reason']='HOLD_INCOMPLETE'
                    else:
                        reconstruction=review_observation(hold)
                        previous=evaluated
                        unchanged=True
                        for sample in hold['samples']:
                            begin=round(sample['request_started_monotonic_s']*1e9)
                            end=round(sample['response_finished_monotonic_s']*1e9)
                            if not previous<=begin<=end or end-previous>1_000_000_000:
                                unchanged=False
                            if [sample['joints_rad'][j] for j in JOINTS]!=verdict['final_pose_rad']:
                                unchanged=False
                            previous=end
                        if (not unchanged or reconstruction['response_span_s']<34
                                or reconstruction['maximum_response_gap_ms']>1000):
                            result['reason']='HOLD_NOT_VERIFIED'
                        else:
                            result.update(status='EXPERIMENT_VERIFIED',reason=verdict['classification'],
                                          hold_reconstruction=reconstruction)
    except Exception:
        # Exceptions never cause an automatic retry; avoid exporting arbitrary text.
        result.update(status='STOPPED',reason='EVIDENCE_OR_OPERATION_FAILED')
    try:
        export(deepcopy(result))
        result['export_succeeded']=True
    except Exception:
        result.update(status='STOPPED',reason='EXPORT_FAILED',export_succeeded=False)
    return result
