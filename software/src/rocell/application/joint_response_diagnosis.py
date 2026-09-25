"""Describe reported single-joint response without assuming fresh encoders.

This is diagnosis, never motion admission or a compensation-training permit.
An HTTP acknowledgment is not proof that the servo received its target.
"""
import math


def diagnose_joint_response(report):
    run=report.get('run') or {};tx=run.get('transaction') or {}
    result=dict(schema='rocell.joint_response_diagnosis.v1',
        classification='INSUFFICIENT_EVIDENCE',motion_authorized=False,
        encoder_freshness_verified=False,physical_cause_identified=False,
        automatic_retry_allowed=False,compensation_training_authorized=False)
    command=tx.get('command') or {};rows=tx.get('rows') or []
    if command.get('T')!=101 or command.get('joint') not in (3,4) or not rows:
        return result
    if run.get('error') is not None or run.get('acknowledgment_received') is not True:
        return dict(result,classification='COMMAND_OR_FEEDBACK_UNCERTAIN')
    originals=run.get('feedback_originals') or []
    if any(s.get('status')!='SUCCEEDED' for s in originals):
        return dict(result,classification='COMMAND_OR_FEEDBACK_UNCERTAIN')
    baseline=tx.get('baseline_joints') or []
    positions=[r[3] for r in rows]
    if (len(baseline)!=6 or any(len(p)!=6 for p in positions)
            or any(type(v) not in (float,int) or not math.isfinite(v)
                   for p in [baseline,*positions] for v in p)
            or type(command.get('rad')) not in (float,int) or not math.isfinite(command['rad'])):
        raise ValueError('Complete finite joint records required')
    index=command['joint']-1;desired=command['rad']-baseline[index]
    deltas=[p[index]-baseline[index] for p in positions]
    if abs(desired)<=1e-8:
        category='NO_DISPLACEMENT_REQUESTED'
    elif any(abs(p[i]-baseline[i])>1e-8 for p in positions for i in range(6) if i!=index):
        category='OTHER_JOINT_REPORTED_CHANGE'
    elif max(map(abs,deltas))<=1e-8:
        category='NO_REPORTED_RESPONSE'
    elif any(v*desired < -1e-8 for v in deltas):
        category='OPPOSITE_REPORTED_RESPONSE'
    else:
        category='SAME_DIRECTION_REPORTED_RESPONSE'
    return dict(result,classification=category,joint=command['joint'],
        requested_delta_rad=desired,reported_final_delta_rad=deltas[-1],
        maximum_reported_delta_rad=max(map(abs,deltas)),
        final_wire_residual_rad=positions[-1][index]-command['rad'],
        sample_count=len(rows),distinct_reported_joint_positions=len(set(p[index] for p in positions)),
        source_endpoint_status=report.get('status'),
        endpoint_success_is_separate=True)
