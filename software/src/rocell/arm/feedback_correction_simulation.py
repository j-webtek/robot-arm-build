"""Finite, hardware-free correction experiments; no live sender or admission.

Plant responses below are hypotheses, not fitted mechanical models. The existing
transaction constructor is consulted only as a pure current-policy check.
"""
import math

from .discrete_transaction import DiscreteTransaction


def simulate(windows, *, tolerance_deg=.05, enforce_current_policy=True,
             desired_deg=1.5, initial_command_deg=1.25, max_corrections=3):
    """Each window is a full hypothetical post-command observation, in degrees.

Correction changes the previous command by a clipped residual, NOT by repeatedly
adding an absolute desired angle. Every hypothetical correction needs a new
complete hold. No retries follow missing/invalid evidence.
"""
    if (type(enforce_current_policy) is not bool or type(max_corrections) is not int
            or not 0<=max_corrections<=3 or type(tolerance_deg) not in (int,float)
            or not math.isfinite(tolerance_deg) or not 0<tolerance_deg<=.5
            or any(type(v) not in (int,float) or not math.isfinite(v) or abs(v)>3
                   for v in (desired_deg,initial_command_deg))):
        raise ValueError('Finite bounded simulation settings required')
    command=initial_command_deg;events=[];previous_error=None;corrections=0
    status='INSUFFICIENT_OBSERVATION_WINDOWS'
    # At most the initial hold plus three correction holds; never unbounded input.
    for window in windows[:max_corrections+1]:
        values=window.get('values_deg',[])
        interval=window.get('sample_interval_s')
        if window.get('transport_clean') is not True:
            status='TRANSPORT_FAULT';break
        if (type(values) not in (list,tuple) or not 3<=len(values)<=1000
                or any(type(v) not in (int,float) or not math.isfinite(v) or abs(v)>3 for v in values)
                or type(interval) not in (int,float) or not math.isfinite(interval) or not 0<interval<=1):
            status='INVALID_OR_STALE_FEEDBACK';break
        if (len(values)-1)*interval<35:
            status='INCOMPLETE_HOLD';break
        error=desired_deg-values[-1]
        event=dict(command_deg=command,final_deg=values[-1],error_deg=-error,
            max_absolute_error_deg=max(abs(desired_deg-v) for v in values),
            reported_span_deg=max(values)-min(values))
        events.append(event)
        if event['max_absolute_error_deg']<=tolerance_deg:
            status='SIMULATED_SUSTAINED_BAND_MET';break
        # A quiet final sample does not erase earlier out-of-band observations.
        if abs(error)<=tolerance_deg:
            status='MORE_HOLD_EVIDENCE_REQUIRED';break
        if corrections>=max_corrections:
            status='CORRECTION_BUDGET_EXHAUSTED';break
        if previous_error is not None and abs(error)>=previous_error-1e-9:
            status='NO_IMPROVEMENT';break
        adjustment=max(-.1,min(.1,error))
        proposed=command+adjustment
        event.update(proposed_command_deg=proposed,command_adjustment_deg=adjustment)
        if abs(proposed)>3:
            status='COMMAND_LIMIT';break
        try:
            DiscreteTransaction(baseline=[0,0,1,0,math.radians(values[-1]),3],
                baseline_finished_ns=1,target=math.radians(proposed),
                desired_endpoint=math.radians(desired_deg),completion_budget_ns=10_000_000_000)
            admitted=True
        except ValueError:
            admitted=False
        event['current_transaction_policy_admissible']=admitted
        if enforce_current_policy and not admitted:
            status='CURRENT_POLICY_REJECTS_CORRECTION';break
        event['hypothetical_only']=True
        command=proposed;corrections+=1;previous_error=abs(error)
    return dict(schema='rocell.feedback_correction_simulation.v1',status=status,
        tolerance_deg=tolerance_deg,enforce_current_policy=enforce_current_policy,
        events=events,simulated_corrections=corrections,hardware_access=False,
        native_commands_sent=0,motion_authorized=False,physical_accuracy_verified=False)


def window(values):
    return dict(values_deg=values,sample_interval_s=.5,transport_clean=True)


def scenarios():
    """Observation-derived starting alternatives, then deliberately synthetic plants."""
    low=1.4062500225647818;near=1.4941406024222599
    stable=window([low]*71)
    late=window([near]*12+[low]*59)
    good=window([1.5]*71)
    cases=[
        ('current_policy', [stable], dict(), 'CURRENT_POLICY_REJECTS_CORRECTION'),
        ('late_change_current_policy',[late],dict(),'CURRENT_POLICY_REJECTS_CORRECTION'),
        ('hypothetical_unit_gain',[stable,good],dict(enforce_current_policy=False),'SIMULATED_SUSTAINED_BAND_MET'),
        ('hypothetical_deadband',[stable,stable],dict(enforce_current_policy=False),'NO_IMPROVEMENT'),
        ('hypothetical_wrong_direction',[stable,window([1.3]*71)],dict(enforce_current_policy=False),'NO_IMPROVEMENT'),
        ('hypothetical_transport_loss',[stable,dict(transport_clean=False)],dict(enforce_current_policy=False),'TRANSPORT_FAULT'),
        ('illustrative_point_one_band',[late],dict(tolerance_deg=.1),'SIMULATED_SUSTAINED_BAND_MET'),
        ('insufficient_hold',[window([near]*3)],dict(),'INCOMPLETE_HOLD'),
        ('returned_to_band',[window([low]*12+[near]*59)],dict(),'MORE_HOLD_EVIDENCE_REQUIRED'),
    ]
    return [dict(name=name,expected=expected,passed=(r:=simulate(w,**kw))['status']==expected,
                 result=r) for name,w,kw,expected in cases]
