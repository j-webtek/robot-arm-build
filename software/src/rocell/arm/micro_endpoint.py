"""Offline verifier for the proposed single wrist-roll micro experiment.

Reported settling is separate from desired accuracy and physical movement.
No sender, admission consumption, retry, or automatic next command exists here.
All angles in this module are radians; host timestamps are integer nanoseconds.
"""
import math


def _pose(pose):
    return (type(pose) in (list,tuple) and len(pose)==6 and
            all(type(v) in (int,float) and math.isfinite(v) and abs(v)<=100 for v in pose))


def verify_micro_endpoint(rows, *, baseline, dispatch_ns, receipt_ns, evaluated_ns,
                          transport_clean=True, cancelled=False):
    """Evaluate all feedback, including faults occurring after apparent settling.

    Require >=2 seconds of post-receipt observations before declaring settling,
    not merely a fast unchanged three-packet prefix. This provisional interval
    is not proof that a servo completed execution. A full passive hold is still
    required by the proposed experiment. Completion budget includes receipt time.
    """
    if (not _pose(baseline) or not 1.35<=math.degrees(baseline[4])<=1.45
            or any(type(t) is not int for t in (dispatch_ns,receipt_ns,evaluated_ns))
            or not 0<dispatch_ns<=receipt_ns<=evaluated_ns
            or type(transport_clean) is not bool or type(cancelled) is not bool):
        raise ValueError('Bounded baseline and ordered explicit timing required')
    result=dict(schema='rocell.micro_endpoint.v1',status='NOT_YET_SETTLED',
        reported_settled=False,desired_band_met=False,physical_accuracy_verified=False,
        motion_authorized=False,automatic_next_command_allowed=False,
        automatic_retry_allowed=False,full_passive_hold_required=True,
        desired_endpoint_rad=math.radians(1.25),command_target_rad=math.radians(.90),
        dispatch_ns=dispatch_ns,receipt_ns=receipt_ns,evaluated_ns=evaluated_ns)
    records=[];previous=receipt_ns;gap=receipt_ns-dispatch_ns;invalid=False
    drift=False;excursion=False
    try:
        for row in rows:
            begin,end,pose=row
            if (len(records)>=4096 or type(begin) is not int or type(end) is not int
                    or not previous<=begin<=end<=evaluated_ns or not _pose(pose)):
                invalid=True;break
            gap=max(gap,end-previous);previous=end
            drift=drift or any(abs(pose[j]-baseline[j])>math.radians(.1) for j in (0,1,2,3,5))
            excursion=excursion or abs(pose[4]-baseline[4])>math.radians(.25) or abs(pose[4])>math.radians(3)
            records.append((begin,end,tuple(pose)))
    except (ValueError,TypeError):
        invalid=True
    gap=max(gap,evaluated_ns-previous)
    result.update(sample_count=len(records),maximum_feedback_gap_ns=gap)
    if cancelled:status='CANCELLED'
    elif not transport_clean:status='TRANSPORT_FAULT'
    elif invalid:status='FEEDBACK_INVALID'
    elif drift:status='OTHER_JOINT_DRIFT'
    elif excursion:status='ROLL_EXCURSION'
    elif gap>1_000_000_000:status='FEEDBACK_GAP_EXCEEDED'
    elif evaluated_ns>dispatch_ns+10_000_000_000:status='COMPLETION_DEADLINE_EXCEEDED'
    else:
        tail=records[-3:]
        settled=(len(tail)==3 and records[-1][1]-receipt_ns>=2_000_000_000
                 and tail[-1][1]-tail[0][1]>=200_000_000
                 and max(r[2][4] for r in tail)-min(r[2][4] for r in tail)<=math.radians(.01))
        if settled:
            final=tail[-1][2][4];desired=math.radians(1.25)
            old_error=baseline[4]-desired;error=final-desired
            in_band=abs(error)<=math.radians(.05)
            if in_band:classification='IN_DESIRED_BAND'
            elif (baseline[4]-desired)*(final-desired)<0:classification='OVERSHOOT'
            elif abs(final-baseline[4])<math.radians(.01):classification='UNCHANGED_OR_SUBRESOLUTION'
            elif abs(error)<abs(old_error)-math.radians(.01):classification='IMPROVED_OUTSIDE_BAND'
            else:classification='NOT_IMPROVED'
            result.update(reported_settled=True,desired_band_met=in_band,
                classification=classification,final_pose_rad=list(tail[-1][2]),
                signed_displacement_deg=math.degrees(final-baseline[4]),
                before_error_deg=math.degrees(old_error),after_error_deg=math.degrees(error))
            status='REPORTED_SETTLED'
        elif evaluated_ns>=dispatch_ns+10_000_000_000:status='COMPLETION_DEADLINE_EXCEEDED'
        else:status='NOT_YET_SETTLED'
    result['status']=status
    return result
