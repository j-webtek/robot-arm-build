"""One-command deadline-driven orchestration; no default transport or auto-run.

The caller owns the continuous lease, bound session and fresh staged admission.
No wizard registration exists. Tests inject virtual I/O and original-format
synthetic feedback. This runner never selects a predecessor or retries one.
"""
from copy import deepcopy
from rocell.application.first_motion_contract import canonical
from rocell.application.micro_endpoint_review import review_micro_feedback,JOINTS
from rocell.providers.windows.arm_wifi_feedback import ADDRESS,MAC
from rocell.providers.windows.arm_wifi_observation import review_observation
from rocell.safety.micro_command_admission import MicroCommandAdmission


def run_micro_transaction(admission,*,transport,clock_ns,wait,observe_hold,export,cancelled=lambda:False):
    if type(admission) is not MicroCommandAdmission:raise ValueError('Exact staged admission required')
    result=dict(schema='rocell.micro_hardware_transaction.v1',status='STOPPED',phase='ADMISSION',
                command_send_attempted=False,feedback_originals=[],hold=None,receipt=None,
                export_succeeded=False,automatic_retry_allowed=False,automatic_next_command_allowed=False,
                physical_accuracy_verified=False)
    last=None
    def now():
        nonlocal last
        value=clock_ns()
        if type(value) is not int or value<=0 or last is not None and value<last:
            raise ValueError('Monotonic host clock required')
        last=value;return value
    try:
        context=admission.snapshot();result['context']=context
        admission.consume(context['command'],now_ns=now(),observed_mac=transport.identity(),cancelled=cancelled())
        result['phase']='SEND'
        dispatch=now()
        if cancelled() or dispatch>context['expires_ns']:raise ValueError('Expired/cancelled before send')
        result.update(command_send_attempted=True,dispatch_ns=dispatch)
        accepted=transport.send_once(canonical(context['command']),deadline_ns=dispatch+800_000_000,cancelled=cancelled)
        receipt=now();result['receipt_ns']=receipt
        if accepted is not True or receipt>dispatch+800_000_000:raise ValueError('Uncertain receipt')
        result['phase']='ENDPOINT';previous=receipt
        for _ in range(100):
            if cancelled():raise ValueError('Cancelled')
            deadline=min(previous+1_000_000_000,dispatch+10_000_000_000)
            wait(min(.15,max(0,(deadline-now())/1e9)))
            if cancelled() or now()>=deadline:raise ValueError('Feedback deadline')
            sample=transport.feedback(deadline_ns=min(deadline,now()+800_000_000),cancelled=cancelled)
            result['feedback_originals'].append(deepcopy(sample))
            evaluated=now()
            if (evaluated>deadline or sample.get('status')!='SUCCEEDED' or sample.get('address')!=ADDRESS
                    or sample.get('expected_mac')!=MAC or sample.get('identity_before_matched') is not True
                    or sample.get('identity_after_matched') is not True or sample.get('cleanup_confirmed') is not True):
                raise ValueError('Feedback failure')
            verdict=review_micro_feedback(result['feedback_originals'],
                baseline=[context['baseline']['joints_rad'][j] for j in JOINTS],
                dispatch_ns=dispatch,receipt_ns=receipt,evaluated_ns=evaluated)
            result['endpoint']=verdict
            previous=round(sample['response_finished_monotonic_s']*1e9)
            if verdict['reported_settled']:break
            if verdict['status']!='NOT_YET_SETTLED':raise ValueError('Endpoint fault')
        else:raise ValueError('Sample limit')
        result['phase']='HOLD'
        if cancelled():raise ValueError('Cancelled before hold')
        hold=observe_hold(cancelled=cancelled);result['hold']=deepcopy(hold)
        if cancelled() or hold.get('status')!='SUCCEEDED':raise ValueError('Incomplete hold')
        reconstructed=review_observation(hold)
        if reconstructed['response_span_s']<34 or reconstructed['maximum_response_gap_ms']>1000:
            raise ValueError('Insufficient hold')
        for sample in hold['samples']:
            begin=round(sample['request_started_monotonic_s']*1e9)
            end=round(sample['response_finished_monotonic_s']*1e9)
            if (not previous<=begin<=end<=now() or end-previous>1_000_000_000
                    or [sample['joints_rad'][j] for j in JOINTS]!=verdict['final_pose_rad']):
                raise ValueError('Changed or unordered hold')
            previous=end
        result.update(status='EXPERIMENT_VERIFIED',classification=verdict['classification'],
                      hold_reconstruction=reconstructed)
    except Exception:
        result.update(status='STOPPED',reason='TRANSACTION_INTERRUPTED_OR_UNCERTAIN')
    result['receipt']=deepcopy(getattr(transport,'receipt',None))
    try:
        export(deepcopy(result));result['export_succeeded']=True
    except Exception:
        result.update(status='STOPPED',reason='EXPORT_FAILED')
    return result
