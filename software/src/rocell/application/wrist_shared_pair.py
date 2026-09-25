"""Two named local wrist endpoints, not a general trajectory or cycle sender."""
import hashlib
import math
from .first_motion_contract import canonical
from .controller_route_preview import _baseline
from rocell.kinematics.firmware_reference import forward

LOW=-.068
HIGH=-.052155347


def pair_candidate(leg):
    if leg not in ('down','up'):raise ValueError('Named pair leg required')
    down=leg=='down'
    bias=.01697605377991493 if down else -.004704207779914954
    desired=LOW if down else HIGH
    record=dict(schema='rocell.wrist_shared_pair.v1',leg=leg,desired_joint_index=3,
        desired_rad=desired,command_rad=desired-bias,training_residual_rad=bias,
        start_center_rad=HIGH if down else LOW,start_tolerance_rad=.0028,
        training_export='wizard-20260917T175637612429Z-34ef0ef0e9484ef7810967bb31445882' if down else
                        'wizard-20260917T180217981403Z-efa28b4ae1f64b19b7a1382dbcc48c75',
        spd=20,acc=1,globally_enabled=False,physical_accuracy_verified=False)
    return dict(record,candidate_sha256=hashlib.sha256(canonical(record)).hexdigest())


def preview_pair_leg(feedback,leg):
    c=pair_candidate(leg);start,joints,consistent=_baseline(feedback)
    fixed=(.001533981,.033747577,1.636757501,None,.018407769,3.138524692)
    if (not consistent or abs(joints[3]-c['start_center_rad'])>c['start_tolerance_rad']
            or any(abs(v-fixed[i])>1e-8 for i,v in enumerate(joints) if i!=3)):
        raise ValueError('Fresh shared-endpoint posture required')
    samples=[]
    # Screen both intended and transmitted sweeps; neither is physical clearance.
    for target_angle in (c['desired_rad'],c['command_rad']):
        for i in range(41):
            q=list(joints);q[3]=joints[3]+(target_angle-joints[3])*i/40
            if i==40:q[3]=target_angle
            p=forward(*q[:4])
            if abs(q[3]-joints[3])>math.radians(3) or math.dist(start[:3],p[:3])>6:
                raise ValueError('Shared-pair sweep exceeds local envelope')
            samples.append(dict(joints_rad=q,xyz_pitch=list(p)))
    return dict(status='PREVIEW_ONLY_NOT_EXECUTABLE',starting_pose=start,
        target_pose=samples[-1]['xyz_pitch'],target_joints_rad=samples[-1]['joints_rad'],
        samples=samples,local_candidate=c,compensation_applied=True,motion_authorized=False,
        physical_accuracy_verified=False)
