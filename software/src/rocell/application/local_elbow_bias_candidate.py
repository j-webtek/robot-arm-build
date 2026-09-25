"""Two-point constant-bias hypothesis, limited to increasing T101 elbow motion."""
import hashlib
import math
from .first_motion_contract import canonical
from .asynchronous_response_review import review_response_envelope


def frozen_candidate():
    """Validate the frozen candidate identity; never fit at dispatch time."""
    from pathlib import Path
    from .product_ghost_export_review import _read
    report,digest=_read(Path(__file__).resolve().parents[3]/'runs/wizard-exports',
        'wizard-20260917T212020172869Z-06f35d9099a14ce8843f0fc62d89bede',
        'attachment-local-elbow-bias.json')
    c=report['candidate'];unsigned={k:v for k,v in c.items() if k!='candidate_sha256'}
    expected='2094c8e20d62dff40e2c29b7fd1f51c8be86b33f6bf2887821186e8866aa8fd9'
    if c.get('candidate_sha256')!=expected or hashlib.sha256(canonical(unsigned)).hexdigest()!=expected:
        raise ValueError('Frozen elbow candidate changed')
    return dict(c,source_sha256=digest)


def build_candidate(model,trials):
    if len(trials)!=2:raise ValueError('Two local identification points required')
    residuals=[];wire_steps=[];observed_steps=[]
    for trial in trials:
        c=trial['command'];r=trial['elbow']
        if (c['T']!=101 or c['joint']!=3 or c['spd']!=20 or c['acc']!=1
                or trial['maximum_other_joint_change_rad']>1e-8):
            raise ValueError('Same-setting isolated elbow evidence required')
        values=(r['ideal_error_rad'],r['ideal_delta_deg'],r['reported_delta_deg'])
        if any(type(v) not in (int,float) or not math.isfinite(v) or v<=0 for v in values):
            raise ValueError('Finite same-direction responses and positive residuals required')
        residuals.append(values[0]);wire_steps.append(math.radians(values[1]))
        observed_steps.append(math.radians(values[2]))
    if max(residuals)-min(residuals)>2*math.pi/4096:
        raise ValueError('Local residual spread exceeds one nominal count')
    if any(abs(a-b)>1e-8 for a,b in zip(trials[0]['final_joints_rad'],trials[1]['baseline_joints_rad'])):
        raise ValueError('Adjacent local experiments required')
    start=list(trials[-1]['final_joints_rad']);desired=list(start);wire=list(start)
    bias=sum(residuals)/2
    desired_step=.014  # Predeclared held-out response, not a training endpoint.
    wire_step=desired_step-bias
    if not (min(wire_steps)<wire_step<max(wire_steps)
            and min(observed_steps)<desired_step<max(observed_steps)):
        raise ValueError('Held-out amplitude would extrapolate beyond sampled ranges')
    desired[2]+=desired_step;wire[2]+=wire_step
    envelopes={name:review_response_envelope(model,start,q,extra_steps=1)
        for name,q in (('wire',wire),('desired',desired))}
    if any(r['status']!='NO_SAMPLED_EXCEEDANCE' for r in envelopes.values()):
        raise ValueError('Wire or expected response envelope rejected')
    candidate=dict(schema='rocell.local_elbow_bias_candidate.v1',
        model_type='CONSTANT_ADDITIVE_BIAS_TWO_LOCAL_POINTS',training_residuals_rad=residuals,
        mean_residual_rad=bias,training_wire_steps_rad=wire_steps,
        training_observed_steps_rad=observed_steps,baseline_joints_rad=start,
        desired_joints_rad=desired,transmitted_joints_rad=wire,
        command=dict(T=101,joint=3,rad=wire[2],spd=20,acc=1),envelopes=envelopes,
        motion_authorized=False,physical_accuracy_verified=False,
        prospectively_validated=False,posture_transfer_unvalidated=True)
    return dict(candidate,candidate_sha256=hashlib.sha256(canonical(candidate)).hexdigest())
