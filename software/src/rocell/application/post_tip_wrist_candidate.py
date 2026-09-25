"""Offline, direction-specific wrist bias hypothesis; no hardware authority."""
import hashlib
import math
from pathlib import Path

from .coordinated_trace_review import review_coordinated_trace
from .first_motion_contract import canonical
from .wrist_tip_review import modeled_tip
from rocell.geometry import UrdfModel
from rocell.kinematics.firmware_reference import forward

SOURCE = 'wizard-20260917T190917013883Z-949dfe33aefa475c83a6103de6fff839'
SOURCE_SHA256 = 'a0821e1036256dfbe8d98181d4eed79869f5e4682fd27019a402bd31bd9513eb'
REVERSE_SOURCE = 'wizard-20260917T191656675614Z-0b1fef1e816a4c11abc7ff289f2a78b1'
REVERSE_SOURCE_SHA256 = 'ecd19db5709c72bb04e2e5090bd82f5b5cb30d4d1e84cfa5d71bb769499bacb9'


def preview_frozen_candidate(feedback, *, reverse=False, post_overshoot=False):
    """Load the reviewed artifact; never fit a correction during dispatch."""
    from .product_ghost_export_review import _read
    from .controller_route_preview import _baseline
    root=Path(__file__).resolve().parents[3]/'runs/wizard-exports'
    if type(reverse) is not bool or type(post_overshoot) is not bool or (reverse and post_overshoot):
        raise ValueError('Explicit exclusive candidate scope required')
    export_id='wizard-20260917T192045698291Z-b3689dd2a3af49e6aadbd7a37bf8febf' if reverse else 'wizard-20260917T191119271010Z-1adad8f0b95e46e995f3c89967081e06'
    c,_=_read(root,export_id,
              'attachment-post-tip-wrist-candidate.json')
    expected='7aff3b4ac17b7c6d24843192a57426fab456508c74d2328e442a989e3134c834'
    if reverse:expected='376e3e9352a23da6e447d2d4850ff7411a9d5fdffe9d7c7125661bdbfdea8dbf'
    unsigned={k:v for k,v in c.items() if k!='candidate_sha256'}
    if c.get('candidate_sha256')!=expected or hashlib.sha256(canonical(unsigned)).hexdigest()!=expected:
        raise ValueError('Frozen wrist candidate changed')
    if post_overshoot:c=transfer_post_overshoot_candidate(c)
    start,joints,consistent=_baseline(feedback)
    if not consistent or any(abs(a-b)>1e-8 for a,b in zip(joints,c['baseline_joints_rad'])):
        raise ValueError('Frozen wrist candidate exact start required')
    return dict(status='PREVIEW_ONLY_NOT_EXECUTABLE',starting_pose=start,
        target_pose=c['wire_pose'],target_joints_rad=c['wire_joints_rad'],
        hypothetical_tip_sweep_mm=c['hypothetical_tip_sweep_mm'],
        local_candidate=c,compensation_applied=True,motion_authorized=False)


def transfer_post_overshoot_candidate(parent):
    """Freeze one posture transfer, retaining the original scalar correction.

    No fitting uses the new-posture trial. Recompute geometry, not coefficients;
    the transfer is an unvalidated hypothesis until its own held-out trial passes.
    """
    expected='7aff3b4ac17b7c6d24843192a57426fab456508c74d2328e442a989e3134c834'
    unsigned={k:v for k,v in parent.items() if k!='candidate_sha256'}
    if parent.get('candidate_sha256')!=expected or hashlib.sha256(canonical(unsigned)).hexdigest()!=expected:
        raise ValueError('Transfer requires unchanged frozen decreasing candidate')
    c=dict(unsigned,parent_candidate_sha256=expected,
           transfer_experiment='WRIST_ELBOW_POSTURE_TRANSFER_V1')
    for key in ('baseline_joints_rad','desired_joints_rad','wire_joints_rad'):
        c[key]=list(parent[key]);c[key][2]=1.691980809
    c['desired_pose']=list(forward(*c['desired_joints_rad'][:4]))
    c['wire_pose']=list(forward(*c['wire_joints_rad'][:4]))
    model=UrdfModel.from_file(Path(__file__).resolve().parents[3]/
        'models/roarm_m3/roarm_m3_kinematic_40dbd84.urdf')
    start=c['baseline_joints_rad'];origin=modeled_tip(model,start)
    initial=forward(*start[:4]);sweep=0.
    for index in range(41):
        q=list(start);q[3]+=(c['command_rad']-start[3])*index/40
        sweep=max(sweep,math.dist(origin,modeled_tip(model,q)))
        if sweep>6 or math.dist(initial[:3],forward(*q[:4])[:3])>6:
            raise ValueError('Transferred candidate exceeds local bound')
    c['hypothetical_tip_sweep_mm']=sweep
    return dict(c,candidate_sha256=hashlib.sha256(canonical(c)).hexdigest())


def build_candidate(report, *, reverse=False):
    """Reject uncertain, opposite, drifting, or cross-joint training evidence."""
    if type(reverse) is not bool:raise ValueError('Explicit candidate direction required')
    run=report['run']; tx=run['transaction']
    scope='POST_TIP_WRIST_RESPONSE_PLUS_1P5_DEGREES_V1' if reverse else 'POST_TIP_WRIST_RESPONSE_MINUS_1P5_DEGREES_V1'
    command_rad=-.045917158220085054 if reverse else -.07833528577991494
    sign=1 if reverse else -1
    if (run.get('error') is not None or not run.get('acknowledgment_received')
            or tx['policy']['scope']!=scope
            or tx['command']!=dict(T=101,joint=4,rad=command_rad,spd=20,acc=1)):
        raise ValueError('Clean named diagnostic required')
    review=review_coordinated_trace(report)
    wrist=review['joints'][3]
    if (review['feedback_failures'] or sign*wrist['requested_delta_deg']<=0
            or sign*wrist['reported_delta_deg']<=0 or (wrist['unchanged_tail_s'] or 0)<1):
        raise ValueError('Settled same-direction evidence required')
    start=tx['baseline_joints']; final=tx['rows'][-1][3]
    if any(abs(a-b)>1e-8 for i,(a,b) in enumerate(zip(start,final)) if i!=3):
        raise ValueError('Other joints changed')
    residual=final[3]-tx['command']['rad']
    if not 0<-sign*residual<math.radians(1):
        raise ValueError('Local residual bound exceeded')
    # Freeze a distinct desired endpoint, not the training endpoint. The move
    # starts from the observed final posture and is a new experiment, not replay.
    # Reverse validation reuses the training start, reached again by the separate
    # decreasing trial; its desired target is held out, not its starting pose.
    candidate_start=list(start if reverse else final)
    desired=list(candidate_start);desired[3]=-.060 if reverse else -.075
    wire=list(desired);wire[3]-=residual
    if not (sign*(wire[3]-desired[3])>0 and sign*(desired[3]-candidate_start[3])>0):
        raise ValueError('Held-out direction changed')
    model=UrdfModel.from_file(Path(__file__).resolve().parents[3]/
        'models/roarm_m3/roarm_m3_kinematic_40dbd84.urdf')
    origin=modeled_tip(model,candidate_start); initial_pose=forward(*candidate_start[:4])
    sweep=0.
    for index in range(41):
        q=list(candidate_start);q[3]+=(wire[3]-candidate_start[3])*index/40
        sweep=max(sweep,math.dist(origin,modeled_tip(model,q)))
        if sweep>6 or math.dist(initial_pose[:3],forward(*q[:4])[:3])>6:
            raise ValueError('Held-out arc exceeds local bound')
    c=dict(schema='rocell.post_tip_wrist_candidate.v1',training_export=REVERSE_SOURCE if reverse else SOURCE,
        training_attachment_sha256=REVERSE_SOURCE_SHA256 if reverse else SOURCE_SHA256,baseline_joints_rad=candidate_start,
        desired_rad=desired[3],command_rad=wire[3],training_residual_rad=residual,
        desired_joints_rad=desired,wire_joints_rad=wire,
        desired_pose=list(forward(*desired[:4])),wire_pose=list(forward(*wire[:4])),
        spd=20,acc=1,model='LOCAL_INCREASING_WRIST_ADDITIVE_RESIDUAL' if reverse else 'LOCAL_DECREASING_WRIST_ADDITIVE_RESIDUAL',
        hypothetical_tip_sweep_mm=sweep,globally_enabled=False,
        held_out_validated=False,repeatability_verified=False,motion_authorized=False)
    return dict(c,candidate_sha256=hashlib.sha256(canonical(c)).hexdigest())
