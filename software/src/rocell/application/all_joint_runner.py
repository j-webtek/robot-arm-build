"""Injected T102 execution composition; no default or native I/O.

Caller owns the transport lock. Transport must enforce deadlines and the native
send latch. Export callback must publish and verify the supplied immutable report.
"""
from rocell.safety.wifi_all_joint_reservation import WifiAllJointReservation, verify_sample
from .joint_diagnostic_assessment import assess_joint_run


def run_all_joint(reservation, *, transport, clock_ns, wait, publish_verified,
                  cancelled=lambda:False):
    if type(reservation) is not WifiAllJointReservation:
        raise ValueError('Exact T102 reservation required')
    tx=reservation.transaction
    if tx.state != 'PREPARED':
        return dict(status='ATTEMPT_ALREADY_USED',transaction=tx.report())
    attempted=False;ack=False;export=None
    try:
        if cancelled():raise ValueError('Cancelled')
        command=tx.dispatch(clock_ns()/1e9)
        payload=reservation.consume(command,now_ns=clock_ns(),
            observed_mac=transport.identity(),cancelled=cancelled())
        attempted=True
        deadline=round((tx.dispatch_s+1)*1e9)
        ack=transport.send_once(payload,deadline_ns=deadline,cancelled=cancelled) is True
        if not ack:raise ValueError('Uncertain delivery')
        tx.acknowledge(clock_ns()/1e9)
        for _ in range(100):
            if tx.state != 'OBSERVING':break
            if cancelled():raise ValueError('Cancelled')
            deadline=round(min(tx.last+1,tx.dispatch_s+10)*1e9)
            wait(min(.15,max(0,(deadline-clock_ns())/1e9)))
            if cancelled():raise ValueError('Cancelled')
            budget=transport.feedback_budget_ns
            if type(budget) is not int or not 0 <= budget <= 1_000_000_000:
                raise ValueError('Invalid feedback budget')
            if clock_ns()>=deadline or deadline-clock_ns()<budget:
                tx.fault('FEEDBACK_OR_COMPLETION_WINDOW_EXHAUSTED');break
            sample=transport.feedback(deadline_ns=deadline,cancelled=cancelled)
            verify_sample(sample)
            begin=sample['request_started_monotonic_s']
            finish=sample['response_finished_monotonic_s']
            if begin<tx.last or finish>clock_ns()/1e9 or clock_ns()>deadline:
                raise ValueError('Feedback window mismatch')
            tx.observe(sample,now_s=finish)
        if tx.state=='OBSERVING':tx.fault('OBSERVATION_LIMIT')
    except Exception:
        # Network exception messages can contain sensitive response data.
        tx.fault('CANCELLED' if cancelled() else 'TRANSACTION_INTERRUPTED_OR_UNCERTAIN')
    report=dict(schema='rocell.all_joint_run.v1',transaction=tx.report(),
        command_send_attempted=attempted,acknowledgment_received=ack,
        move_request=reservation.request(),automatic_retry_allowed=False,
        physical_accuracy_verified=False)
    report['diagnostic_assessment']=assess_joint_run(report)
    try:
        export=publish_verified(report)
        verified=isinstance(export,dict) and export.get('verified') is True
        if tx.state=='REPORTED_SETTLED_PENDING_EXPORT':tx.finish_export(verified=verified)
    except Exception:
        tx.fault('EXPORT_NOT_VERIFIED')
    return dict(report,status=tx.state,transaction=tx.report(),export=export)
