"""Offline prospective joint-response trial, not a vertical keypress or permit."""
import hashlib
import math
from pathlib import Path
from .first_motion_contract import canonical
from .wrist_tip_review import modeled_tip
from rocell.geometry import UrdfModel
from rocell.kinematics.firmware_reference import forward,inverse
from rocell.simulation.controller import ControllerPose,simulate_t104_trace
from rocell.motion.characterization_controller import _screen_reference_trace


def supported_inverse(comparison,training_rows,desired_delta_deg):
    name=comparison['joint'];slope=comparison['slope'];offset=comparison['intercept_deg']
    values=[desired_delta_deg,slope,offset]
    if any(type(v) not in (int,float) or not math.isfinite(v) for v in values) or slope<=0:
        raise ValueError('Finite positive-slope response model required')
    wire=(desired_delta_deg-offset)/slope
    xs=sorted(r[name]['requested_delta_deg'] for r in training_rows)
    ys=sorted(r[name]['reported_delta_deg'] for r in training_rows)
    if len(xs)!=2 or not xs[0]<wire<xs[1] or not ys[0]<desired_delta_deg<ys[1]:
        raise ValueError('Inverse trial would extrapolate outside training support')
    return wire


def build_trial(analysis,start):
    if len(start)!=6 or any(type(v) not in (int,float) or not math.isfinite(v) for v in start):
        raise ValueError('Finite six-joint starting pose required')
    desired=list(start);wire=list(start);details=[]
    for comparison,index,name in zip(analysis['comparisons'],(2,3),('elbow','wrist_pitch')):
        if comparison['joint']!=name:raise ValueError('Unexpected model joint order')
        points=sorted(r[name]['reported_delta_deg'] for r in analysis['rows'][:2])
        # Fixed interior point chosen before any prospective hardware observation.
        delta=points[0]+.6*(points[1]-points[0])
        command=supported_inverse(comparison,analysis['rows'][:2],delta)
        desired[index]+=math.radians(delta);wire[index]+=math.radians(command)
        details.append(dict(joint=name,desired_delta_deg=delta,wire_delta_deg=command))
    start_pose=forward(*start[:4]);wire_pose=forward(*wire[:4])
    trace=simulate_t104_trace(ControllerPose(*start_pose,*start[4:]),
        ControllerPose(*wire_pose,*start[4:]),spd_coefficient=.05,maximum_samples=1024)
    if _screen_reference_trace(trace)['status']!='REFERENCE_IK_PASS':raise ValueError('Reference path rejected')
    model=UrdfModel.from_file(Path(__file__).resolve().parents[3]/'models/roarm_m3/roarm_m3_kinematic_40dbd84.urdf')
    origin=modeled_tip(model,start);sweep=0.
    for sample in trace.samples:
        p=sample.pose;q=[*inverse(p.x_mm,p.y_mm,p.z_mm,p.pitch_rad),*start[4:]]
        sweep=max(sweep,math.dist(origin,modeled_tip(model,q)))
        if sweep>6 or max(abs(a-b) for a,b in zip(q,start))>math.radians(3):raise ValueError('Local bound exceeded')
    desired_tip=modeled_tip(model,desired)
    if math.dist(origin,desired_tip)>6:raise ValueError('Predicted response outside local bound')
    from .asynchronous_response_review import review_response_envelope
    response_review=review_response_envelope(model,start,desired,extra_steps=1)
    if response_review['status']=='SAMPLED_MODEL_BOUND_EXCEEDED':
        raise ValueError('Independent joint-progress stress exceeds local bound; candidate not qualified')
    c=dict(schema='rocell.coordinated_offset_candidate.v1',experiment='COORDINATED_AFFINE_INTERIOR_V1',
        model='FROZEN_AFFINE_DELTA_RESPONSE_INVERSE',baseline_joints_rad=list(start),
        desired_joints_rad=desired,wire_joints_rad=wire,desired_pose=list(forward(*desired[:4])),wire_pose=list(wire_pose),
        speed_coefficient=.05,corrected_joint_indices=[2,3],response_demands=details,
        maximum_hypothetical_wire_tip_sweep_mm=sweep,
        asynchronous_response_stress=response_review,
        predicted_tip_delta_mm=[b-a for a,b in zip(origin,desired_tip)],
        globally_enabled=False,motion_authorized=False,held_out_validated=False,
        physical_accuracy_verified=False,vertical_press_qualified=False,
        limitation='Starting posture and motion-history transfer remain unvalidated.')
    return dict(c,candidate_sha256=hashlib.sha256(canonical(c)).hexdigest())
