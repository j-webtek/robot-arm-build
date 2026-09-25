"""Offline local elbow/wrist offset hypothesis. Never grants motion authority.

One trace estimates bias, not a global model. The next 5 mm waypoint is held out:
only a new physical trial can test whether the fitted residual transfers to it.
"""
import hashlib
import math
from .first_motion_contract import canonical
from .coordinated_trace_review import review_coordinated_trace
from .ghost_first_step import ANCHOR
from rocell.kinematics.firmware_reference import forward, inverse
from rocell.simulation.controller import ControllerPose, simulate_t104_trace
from rocell.motion.characterization_controller import _screen_reference_trace
from .controller_route_preview import _baseline


def frozen_candidate(*, revised=False, tip=False, post_transfer=False, affine=False):
    """Reviewed 17:39 UTC candidate; never fit during dispatch."""
    if type(revised) is not bool:raise ValueError('Explicit candidate version required')
    if type(tip) is not bool or (tip and revised):raise ValueError('Exclusive tip candidate required')
    if type(post_transfer) is not bool or (post_transfer and (not tip or revised)):
        raise ValueError('Exclusive post-transfer candidate required')
    if type(affine) is not bool or (affine and not post_transfer):raise ValueError('Explicit affine scope required')
    if tip:
        # Load only the pinned, verified artifact. Never refit during dispatch or
        # silently select a newer export. Missing/changed evidence fails closed.
        from pathlib import Path
        from .product_ghost_export_review import _read
        root=Path(__file__).resolve().parents[3]/'runs/wizard-exports'
        export_id='wizard-20260917T201134178702Z-e0e999596ce14686be89309aa4918729' if post_transfer else 'wizard-20260917T182802972330Z-29b98ce47f894c32ac40b1b5c66bc0cc'
        if affine:export_id='wizard-20260917T201815261974Z-ed05b78c956046cca2f21cdad0c14675'
        report,_=_read(root,export_id,
                       'attachment-affine-trial.json' if affine else 'attachment-coordinated-candidate.json')
        c=report['candidate']
        expected='5ea61cae132f37e8e424fc137362a64e4e3840db7701a4c0c25725f95ae5712b'
        if post_transfer:expected='563d49058fd7497f46b7441434981e8bc27ae1538055d99cfdb443b7ee4ebd56'
        if affine:expected='c322d3db96a664f86cab305180ba99917154aa4d9c7df75dabcd6da13e121075'
        unsigned={k:v for k,v in c.items() if k!='candidate_sha256'}
        if c.get('candidate_sha256')!=expected or hashlib.sha256(canonical(unsigned)).hexdigest()!=expected:
            raise ValueError('Frozen tip candidate changed')
        return c
    if revised:
        # Fixed constants from the retained plateau and successful read-only
        # recovery. The source's late transport failure remains part of provenance.
        start=[.001533981,.024543693,1.61528177,-.03834952,.018407769,3.138524692]
        pose=forward(*start[:4]);distance=math.dist(pose[:3],ANCHOR[:3])
        desired_pose=[a+(b-a)*5/distance for a,b in zip(pose,ANCHOR)]
        desired=[*inverse(*desired_pose),*start[4:]]
        residual=[0.,0.,.009194895632964384,.015384684885258931,0.,0.]
        wire=[a-b for a,b in zip(desired,residual)]
        c=dict(schema='rocell.coordinated_offset_candidate.v1',experiment_version=2,
            parent_candidate_sha256=frozen_candidate()['candidate_sha256'],
            training_export='wizard-20260917T174213158886Z-8fcb3b9899e54b4d8cf53aa200d4ac51',
            training_attachment_sha256='247599b780c2d4f7cbe98ca0e0e91ee9ba0373fc71f7d473f2826a068aceaaa7',
            training_runner_error='TRANSACTION_INTERRUPTED_OR_UNCERTAIN',
            recovery_export='wizard-20260917T174236602587Z-3135adb51d924cc0ad76cee17ba47314',
            baseline_joints_rad=start,desired_joints_rad=desired,wire_joints_rad=wire,
            residual_rad=residual,desired_pose=desired_pose,wire_pose=list(forward(*wire[:4])),
            speed_coefficient=.05,corrected_joint_indices=[2,3],
            model='LOCAL_DIRECTION_SPECIFIC_ADDITIVE_JOINT_RESIDUAL',globally_enabled=False)
        digest=hashlib.sha256(canonical(c)).hexdigest()
        if digest!='ba64659960c6aec0b134d84ca7541db26849bee25458630a68e8bc16cd47e509':
            raise ValueError('Frozen v2 candidate changed')
        return dict(c,candidate_sha256=digest)
    c=dict(schema='rocell.coordinated_offset_candidate.v1',
        training_trace_sha256='77d278cff80a28e65611a615d9b01971435eba94da1d8a434d48f1f20ada2a62',
        baseline_joints_rad=[.001533981,.015339808,1.590738077,-.010737866,.018407769,3.138524692],
        desired_joints_rad=[.00028257014793878557,.024528814252110176,1.6118796518392413,-.04175411863384329,.018407769,3.138524692],
        wire_joints_rad=[.00028257014793878557,.024528814252110176,1.6060868743670358,-.05373420488525882,.018407769,3.138524692],
        residual_rad=[0.,0.,.005792777472205524,.01198008625141553,0.,0.],
        desired_pose=[351.2729523115827,.09925925274339231,208.7580507729569,.023858020662611754],
        wire_pose=[351.61436785852874,.09935572658756914,212.64044535613206,.006085156938990366],
        speed_coefficient=.05,corrected_joint_indices=[2,3],
        model='LOCAL_DIRECTION_SPECIFIC_ADDITIVE_JOINT_RESIDUAL',globally_enabled=False)
    digest=hashlib.sha256(canonical(c)).hexdigest()
    if digest!='2745b882dd25f533a58d6739ab5580486f78d79ad834fabfec2736c6fbf1aa83':
        raise ValueError('Frozen candidate changed')
    return dict(c,candidate_sha256=digest)


def preview_frozen_candidate(feedback, *, revised=False, tip=False, post_transfer=False, affine=False):
    c=frozen_candidate(revised=revised,tip=tip,post_transfer=post_transfer,affine=affine);start,joints,consistent=_baseline(feedback)
    if not consistent or any(abs(a-b)>1e-8 for a,b in zip(joints,c['baseline_joints_rad'])):
        raise ValueError('Exact held-out starting posture required')
    trace=simulate_t104_trace(ControllerPose(*start,*joints[4:]),
        ControllerPose(*c['wire_pose'],*joints[4:]),spd_coefficient=.05,maximum_samples=1024)
    if _screen_reference_trace(trace)['status']!='REFERENCE_IK_PASS':
        raise ValueError('Frozen reference route rejected')
    if not (c['wire_joints_rad'][2]>joints[2] and c['wire_joints_rad'][3]<joints[3]):
        raise ValueError('Observed direction required')
    bounds=((-math.pi,math.pi),(-math.pi/2,math.pi/2),(0,2.95),(-math.pi/2,math.pi/2))
    if post_transfer:
        from pathlib import Path
        from rocell.geometry import UrdfModel
        from .wrist_tip_review import modeled_tip
        model=UrdfModel.from_file(Path(__file__).resolve().parents[3]/'models/roarm_m3/roarm_m3_kinematic_40dbd84.urdf')
        origin=modeled_tip(model,joints)
    for sample in trace.samples:
        p=sample.pose;solved=inverse(p.x_mm,p.y_mm,p.z_mm,p.pitch_rad)
        if post_transfer and math.dist(origin,modeled_tip(model,[*solved,*joints[4:]]))>6:
            raise ValueError('Transferred candidate exceeds 6 mm tip bound')
        if (max(abs(a-b) for a,b in zip(solved,joints[:4]))>math.radians(3)
                or math.dist(start[:3],(p.x_mm,p.y_mm,p.z_mm))>10
                or not all(lo<=v<=hi for v,(lo,hi) in zip(solved,bounds))):
            raise ValueError('Frozen candidate envelope rejected')
    return dict(status='PREVIEW_ONLY_NOT_EXECUTABLE',starting_pose=start,
        target_pose=c['wire_pose'],target_joints_rad=c['wire_joints_rad'],
        local_candidate=c,sample_count=len(trace.samples),motion_authorized=False,
        compensation_applied=True,physical_accuracy_verified=False)


def preview_coordinated_candidate(report, *, tip_model=None, post_transfer=False):
    if type(post_transfer) is not bool or (post_transfer and tip_model is None):
        raise ValueError('Post-transfer candidate requires explicit tip model')
    review=review_coordinated_trace(report)
    run=report['run']; tx=run['transaction']
    if (tx['command'].get('T')!=104 or tx['command'].get('spd')!=.05
            or tx['policy']['scope']!=('POST_TRANSFER_TIP_PRESS_2MM_V1' if post_transfer else 'LOCAL_HYPOTHETICAL_TIP_PRESS_2MM_V1' if tip_model is not None else 'POST_WRIST_GHOST_APPROACH_5MM_UNCOMPENSATED_V2')
            or run.get('error') is not None or run.get('acknowledgment_received') is not True
            or review['feedback_failures'] or len(tx['rows'])<3):
        raise ValueError('Complete named coordinated evidence required')
    start=list(tx['rows'][-1][3]); expected=tx['expected_joints']
    # Require a sustained reported plateau, not merely the last received point.
    for i in (2,3):
        if (review['joints'][i]['unchanged_tail_s'] or 0)<1:
            raise ValueError('Reported settling evidence required')
        if (expected[i]-tx['baseline_joints'][i])*(start[i]-tx['baseline_joints'][i])<=0:
            raise ValueError('Observed joint direction does not support additive correction')
    if any(abs(a-b)>1e-8 for a,b in zip(start[4:],tx['baseline_joints'][4:])):
        raise ValueError('Uncommanded roll/gripper change')
    starting_pose=forward(*start[:4])
    if tip_model is None:
        distance=math.dist(starting_pose[:3],ANCHOR[:3])
        if not 150<=distance<=220:
            raise ValueError('Outside reviewed local approach')
        desired_pose=[a+(b-a)*5/distance for a,b in zip(starting_pose,ANCHOR)]
        desired=[*inverse(*desired_pose),*start[4:]]
    else:
        from .local_tip_cycle import preview_local_tip_cycle
        tip_reference=preview_local_tip_cycle(tip_model,start)
        if tip_reference['status']!='LOCAL_TIP_REFERENCE_PASS_NOT_EXECUTABLE':
            raise ValueError('Held-out local tip reference rejected')
        # Preserve measured roll/gripper rather than transmitting numerical IK
        # changes to axes not included in this correction experiment.
        desired=[*tip_reference['waypoints'][4]['joints_rad'][:4],*start[4:]]
        desired_pose=list(forward(*desired[:4]))
    residual=[0.,0.,start[2]-expected[2],start[3]-expected[3],0.,0.]
    wire=[value-bias for value,bias in zip(desired,residual)]
    for i in (2,3):
        training_direction=expected[i]-tx['baseline_joints'][i]
        if (training_direction*(desired[i]-start[i])<=0 or
                training_direction*(wire[i]-start[i])<=0 or abs(residual[i])>math.radians(1)):
            raise ValueError('Correction outside observed direction or residual bound')
    wire_pose=forward(*wire[:4])
    trace=simulate_t104_trace(ControllerPose(*starting_pose,*start[4:]),
        ControllerPose(*wire_pose,*start[4:]),spd_coefficient=.05,maximum_samples=1024)
    if _screen_reference_trace(trace)['status']!='REFERENCE_IK_PASS':
        raise ValueError('Corrected reference path rejected')
    bounds=((-math.pi,math.pi),(-math.pi/2,math.pi/2),(0,2.95),(-math.pi/2,math.pi/2))
    maximum_sweep=0.; maximum_joint=0.;maximum_tip_sweep=0.
    if tip_model is not None:
        from .wrist_tip_review import modeled_tip
        tip_origin=modeled_tip(tip_model,start)
    for sample in trace.samples:
        p=sample.pose; solved=inverse(p.x_mm,p.y_mm,p.z_mm,p.pitch_rad)
        maximum_joint=max(maximum_joint,max(abs(a-b) for a,b in zip(solved,start[:4])))
        maximum_sweep=max(maximum_sweep,math.dist(starting_pose[:3],(p.x_mm,p.y_mm,p.z_mm)))
        if tip_model is not None:
            maximum_tip_sweep=max(maximum_tip_sweep,math.dist(tip_origin,modeled_tip(tip_model,[*solved,*start[4:]])))
            if maximum_tip_sweep>(6 if post_transfer else 10):
                raise ValueError('Corrected hypothetical tip sweep exceeds scoped bound')
        if maximum_joint>math.radians(3) or maximum_sweep>10 or not all(lo<=v<=hi for v,(lo,hi) in zip(solved,bounds)):
            raise ValueError('Corrected local sweep rejected')
    candidate=dict(schema='rocell.coordinated_offset_candidate.v1',
        training_trace_sha256=hashlib.sha256(canonical(report)).hexdigest(),
        baseline_joints_rad=start,desired_joints_rad=desired,wire_joints_rad=wire,
        residual_rad=residual,desired_pose=desired_pose,wire_pose=wire_pose,
        speed_coefficient=.05,corrected_joint_indices=[2,3],
        model='LOCAL_DIRECTION_SPECIFIC_ADDITIVE_JOINT_RESIDUAL',globally_enabled=False)
    if tip_model is not None:
        candidate.update(experiment='LOCAL_TIP_PRESS_HELD_OUT_V1',
            desired_tip_mm=tip_reference['waypoints'][4]['tip_mm'],
            hypothetical_tool_offset_mm=-100)
    if post_transfer:
        candidate.update(experiment='POST_TRANSFER_TIP_HELD_OUT_V1',
                         held_out_validated=False,repeatability_verified=False)
    candidate['candidate_sha256']=hashlib.sha256(canonical(candidate)).hexdigest()
    return dict(schema='rocell.coordinated_candidate_preview.v1',
        status='CANDIDATE_REFERENCE_PASS_NOT_EXECUTABLE',candidate=candidate,
        sample_count=len(trace.samples),maximum_reference_sweep_mm=maximum_sweep,
        maximum_joint_excursion_deg=math.degrees(maximum_joint),desired_translation_mm=2 if tip_model is not None else 5,
        maximum_hypothetical_wire_tip_sweep_mm=maximum_tip_sweep if tip_model is not None else None,
        hardware_access=False,motion_authorized=False,physical_accuracy_verified=False,
        full_arm_clearance_verified=False,held_out_validation_required=True,
        prediction_assumption='The observed elbow/wrist bias transfers locally; not yet verified.')
