"""Finite transaction composition with injected I/O; no default/native sender.

Tests supply a simulated transport. A production transport must enforce supplied
absolute deadlines, validate its own identity and hold arm_transport_lock over
the entire call. This module is not registered as a live wizard movement action.
"""
from copy import deepcopy

from rocell.safety.wifi_dispatch_reservation import WifiDispatchReservation
from rocell.providers.windows.arm_wifi_feedback import ADDRESS, MAC
from rocell.providers.windows.arm_wifi_observation import review_observation


def run_reserved_transaction(reservation, *, transport, clock_ns, wait, cancelled=lambda:False):
    if type(reservation) is not WifiDispatchReservation:
        raise ValueError('Exact Wi-Fi dispatch reservation required')
    return _run_transaction(reservation,transport=transport,clock_ns=clock_ns,wait=wait,cancelled=cancelled)


def run_cartesian_transaction(reservation, *, transport, clock_ns, wait, cancelled=lambda:False):
    from rocell.safety.wifi_cartesian_reservation import WifiCartesianReservation
    if type(reservation) is not WifiCartesianReservation:
        raise ValueError('Exact Cartesian reservation required')
    return _run_transaction(reservation,transport=transport,clock_ns=clock_ns,wait=wait,
                            cancelled=cancelled,cartesian=True)


def _run_transaction(reservation, *, transport, clock_ns, wait, cancelled, cartesian=False):
    schema='rocell.wifi_cartesian_run.v1' if cartesian else 'rocell.wifi_discrete_run.v1'
    tx=reservation.transaction
    if tx.snapshot()['state']!='PREPARED':
        return dict(schema=schema,status='ATTEMPT_ALREADY_USED',
            move_request=reservation.request(),
            command_send_attempted=False,acknowledgment_received=False,
            transaction=tx.snapshot(),feedback_originals=[],automatic_retry_allowed=False,
            physical_accuracy_verified=False)
    samples=[];ack=None;error=None;attempted=False;scheduling=[]
    try:
        if cancelled():raise ValueError('Cancelled before dispatch')
        command=tx.begin_dispatch(clock_ns())
        # Burn the durable latch even if the subsequent send raises immediately.
        mac=transport.identity()
        payload=reservation.consume(command,now_ns=clock_ns(),observed_mac=mac,
            cancelled=cancelled())
        attempted=True
        ack=transport.send_once(payload,deadline_ns=tx.next_deadline_ns(),cancelled=cancelled)
        if ack is not True:raise ValueError('Command acknowledgment uncertain')
        tx.acknowledge(clock_ns())
        for _ in range(800):
            if tx.snapshot()['state']!='OBSERVING':break
            if cancelled():tx.fault(clock_ns(),cancelled=True);break
            deadline=tx.next_deadline_ns()
            wait(min(.15,max(0,(deadline-clock_ns())/1e9)))
            if cancelled():tx.fault(clock_ns(),cancelled=True);break
            # No I/O starts at or beyond the active absolute deadline.
            if clock_ns()>=deadline:
                tx.tick(max(clock_ns(),deadline+1));break
            required=getattr(transport,'feedback_budget_ns',0)
            if type(required) is not int or not 0<=required<=1_000_000_000:
                raise ValueError('Invalid observation budget')
            remaining=deadline-clock_ns()
            if remaining<required:
                # Preserve a failed endpoint, without creating a predictably
                # truncated network request. This is not a transport success.
                scheduling.append(dict(reason='INSUFFICIENT_REMAINING_FEEDBACK_BUDGET',
                    remaining_ns=remaining,required_ns=required,deadline_ns=deadline))
                while clock_ns()<deadline:
                    if cancelled():tx.fault(clock_ns(),cancelled=True);break
                    wait(min(.05,(deadline-clock_ns())/1e9))
                if tx.snapshot()['state']=='OBSERVING':tx.tick(clock_ns())
                break
            sample=transport.feedback(deadline_ns=deadline,cancelled=cancelled)
            samples.append(deepcopy(sample))
            if (sample.get('status')!='SUCCEEDED' or sample.get('address')!=ADDRESS or sample.get('expected_mac')!=MAC
                    or not sample.get('identity_before_matched') or not sample.get('identity_after_matched')
                    or not sample.get('cleanup_confirmed')):
                raise ValueError('Feedback transport fault')
            review_observation(dict(schema='rocell.arm_wifi_observation.v4',samples=[sample]))
            row=(round(sample['request_started_monotonic_s']*1e9),
                 round(sample['response_finished_monotonic_s']*1e9),
                 [sample['joints_rad'][k] for k in ('b','s','e','t','r','g')])
            if cartesian:
                values=sample['controller_cartesian']['values']
                row=(row[0],row[1],[values[k] for k in ('x','y','z','tit')],row[2])
            tx.observe(row,clock_ns())
        if tx.snapshot()['state']=='OBSERVING':tx.fault(clock_ns())
    except Exception:
        # Never export exception text, which may include network response data.
        error='TRANSACTION_INTERRUPTED_OR_UNCERTAIN'
        # A Cartesian observation that exhausts its absolute window is a
        # completion/gap failure, not a newly uncertain command receipt. Keep
        # the original transport failure and never reinterpret it as arrival.
        if cartesian and tx.snapshot()['state']=='OBSERVING':
            tx.tick(clock_ns())
        tx.fault(clock_ns(),cancelled=cancelled())
    snapshot=tx.snapshot()
    status=snapshot['state']
    if error and status=='PREPARED':status='CANCELLED_BEFORE_DISPATCH' if cancelled() else 'DISPATCH_NOT_STARTED'
    return dict(schema=schema,status=status,
        move_request=reservation.request(),
        command_send_attempted=attempted,acknowledgment_received=ack is True,
        error=error,transaction=snapshot,feedback_originals=samples,feedback_scheduling=scheduling,
        automatic_retry_allowed=False,physical_accuracy_verified=False)
