"""One-shot discrete transaction state machine, without hardware I/O.

A native adapter must own the transport, enforce absolute I/O deadlines and
consume its existing movement admission before dispatch. This engine is not a
permit and is deliberately not registered as a live Wi-Fi command sender.
"""
from copy import deepcopy
import math

from .discrete_endpoint import MAX_FEEDBACK_GAP_NS, policy, verify_discrete_endpoint


class DiscreteTransaction:
    """Record intent before the one attempted write; never replay uncertain writes."""

    def __init__(self, *, baseline, baseline_finished_ns, target, completion_budget_ns,
                 desired_endpoint=None):
        if (type(baseline) not in (list,tuple) or len(baseline)!=6
                or any(type(v) not in (int,float) or not math.isfinite(v) or abs(v)>100 for v in baseline)
                or type(target) not in (int,float) or not math.isfinite(target)
                or not .5 < abs(math.degrees(target-baseline[4])) <= 1.5
                or abs(math.degrees(target))>3
                or type(baseline_finished_ns) is not int or baseline_finished_ns<=0
                or type(completion_budget_ns) is not int or not 0<completion_budget_ns<=120_000_000_000):
            raise ValueError('Bounded roll target, finite baseline and explicit budget required')
        if desired_endpoint is not None and (
                type(desired_endpoint) not in (int,float) or not math.isfinite(desired_endpoint)
                or abs(math.degrees(desired_endpoint))>3
                or abs(math.degrees(desired_endpoint-target))>.5
                or (desired_endpoint-baseline[4])*(target-baseline[4])<=0):
            raise ValueError('Bounded same-direction desired endpoint required')
        self._desired_endpoint=desired_endpoint
        self._baseline=tuple(baseline); self._baseline_end=baseline_finished_ns
        self._command=dict(T=101,joint=5,rad=target,spd=20,acc=1)
        self._budget=completion_budget_ns
        self._state='PREPARED';self._attempts=0;self._rows=[];self._result=None
        self._dispatch=None;self._finished=None;self._last_event=baseline_finished_ns

    def _time(self, now):
        if type(now) is not int or now<self._last_event:
            raise ValueError('Monotonic host timestamp required')
        self._last_event=now

    def begin_dispatch(self, now):
        self._time(now)
        if self._state!='PREPARED':raise ValueError('Command already consumed or terminal')
        if now-self._baseline_end>MAX_FEEDBACK_GAP_NS:
            self._state='BASELINE_EXPIRED'
            raise ValueError('Fresh baseline required')
        # Consume before returning intent. A sender exception cannot re-enable it.
        self._attempts=1;self._dispatch=now;self._state='DISPATCHING'
        return deepcopy(self._command)

    def acknowledge(self, now):
        self._time(now)
        if self._state!='DISPATCHING':raise ValueError('No pending dispatch')
        if now-self._dispatch>MAX_FEEDBACK_GAP_NS:
            self._state='COMMAND_OUTCOME_UNCERTAIN';return
        self._finished=now;self._state='OBSERVING'

    def fault(self, now, *, cancelled=False):
        self._time(now)
        if self._state in ('DISPATCHING','OBSERVING'):
            self._state='CANCELLED' if cancelled else 'COMMAND_OUTCOME_UNCERTAIN'

    def next_deadline_ns(self):
        if self._state=='DISPATCHING':return self._dispatch+MAX_FEEDBACK_GAP_NS
        if self._state=='OBSERVING':
            last=self._rows[-1][1] if self._rows else self._finished
            return min(last+MAX_FEEDBACK_GAP_NS,self._dispatch+self._budget)
        return None

    def observe(self, row, now):
        self._time(now)
        if self._state!='OBSERVING':raise ValueError('Observation requires acknowledged single dispatch')
        self._rows.append(deepcopy(row))
        self._evaluate(now)

    def tick(self, now):
        self._time(now)
        if self._state=='DISPATCHING' and now>=self.next_deadline_ns():
            self._state='COMMAND_OUTCOME_UNCERTAIN'
        elif self._state=='OBSERVING':self._evaluate(now)

    def _evaluate(self, now):
        # Completion budget includes command-response latency, never resets on ack.
        deadline=self._dispatch+self._budget
        if deadline<=self._finished:
            self._state='COMPLETION_DEADLINE_EXCEEDED';return
        endpoint_args = {} if self._desired_endpoint is None else dict(command_target=self._command['rad'])
        self._result=verify_discrete_endpoint(self._rows,joint='r',start=self._baseline,
            target=self._command['rad'] if self._desired_endpoint is None else self._desired_endpoint,
            **endpoint_args,command_finished_ns=self._finished,
            completion_deadline_ns=deadline,evaluated_ns=now)
        status=self._result['status']
        if status!='NOT_YET_VERIFIED':self._state=status

    def snapshot(self):
        result = dict(schema='rocell.discrete_transaction.v1',state=self._state,
            command=self._command,command_attempts=self._attempts,baseline=self._baseline,
            baseline_finished_ns=self._baseline_end,dispatch_started_ns=self._dispatch,
            acknowledgment_finished_ns=self._finished,completion_budget_ns=self._budget,
            rows=self._rows,result=self._result,policy=policy(),
            automatic_retry_allowed=False,automatic_return_allowed=False,
            automatic_next_command_allowed=False,physical_accuracy_verified=False,
            motion_authorized=False)
        if self._desired_endpoint is not None:
            result.update(schema='rocell.discrete_transaction.v2',desired_endpoint_rad=self._desired_endpoint)
        return deepcopy(result)


def simulate_transactions():
    """Finite deterministic suite for the wizard; all commands stay in memory."""
    scenarios={
        'normal':'REPORTED_ENDPOINT_VERIFIED',
        'lost_ack_after_execution':'COMMAND_OUTCOME_UNCERTAIN',
        'feedback_reset':'COMMAND_OUTCOME_UNCERTAIN',
        'feedback_silence':'FEEDBACK_GAP_EXCEEDED',
        'missed_target':'COMPLETION_DEADLINE_EXCEEDED',
        'other_joint_drift':'OTHER_JOINT_CHANGED',
        'cancelled':'CANCELLED',
    }
    results=[]
    for name,expected in scenarios.items():
        target=math.radians(1)
        tx=DiscreteTransaction(baseline=[0,0,1,0,0,3],baseline_finished_ns=1_000_000_000,
            target=target,completion_budget_ns=3_000_000_000)
        intent=tx.begin_dispatch(1_010_000_000)
        # Simulated device may execute even if its acknowledgment is lost.
        if name=='lost_ack_after_execution':tx.tick(2_010_000_000)
        else:
            tx.acknowledge(1_060_000_000)
            if name=='feedback_reset':tx.fault(1_360_000_000)
            elif name=='cancelled':tx.fault(1_360_000_000,cancelled=True)
            elif name=='feedback_silence':tx.tick(2_060_000_001)
            else:
                for index in range(1,12):
                    now=1_060_000_000+index*300_000_000
                    pose=[.1 if name=='other_joint_drift' else 0,0,1,0,
                          0 if name=='missed_target' else target,3]
                    tx.observe((now-10_000_000,now,pose),now)
                    if tx.snapshot()['state']!='OBSERVING':break
        snapshot=tx.snapshot()
        results.append(dict(scenario=name,expected=expected,
            passed=snapshot['state']==expected,transaction=snapshot,
            simulated_device_executed=name=='lost_ack_after_execution',
            simulated_wire_intent=intent))
    return dict(schema='rocell.discrete_transaction_simulation.v1',
        status='SUCCEEDED' if all(r['passed'] for r in results) else 'FAILED',
        scenarios=results,hardware_access=False,motion_commands=0,
        physical_authority=False,movement_ready=False)
