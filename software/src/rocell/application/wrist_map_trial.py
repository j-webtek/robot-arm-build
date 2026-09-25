"""Named one-leg mapping preparation and held-out preview; no automatic chain."""
import hashlib
import math
from pathlib import Path
from .controller_route_preview import _baseline
from .first_motion_contract import canonical
from .product_ghost_export_review import _read
from .local_wrist_response_map import predict_command
from .wrist_tip_review import modeled_tip
from rocell.geometry import UrdfModel
from rocell.kinematics.firmware_reference import forward


def preview_map_trial(feedback, *, preparation=False, cycle_entry=False, posture_transfer=False):
    if type(preparation) is not bool:raise ValueError('Explicit trial selection required')
    if type(cycle_entry) is not bool or (cycle_entry and not preparation):raise ValueError('Exclusive cycle entry required')
    if type(posture_transfer) is not bool or (posture_transfer and preparation and not cycle_entry):
        raise ValueError('Exclusive posture transfer required')
    start,joints,consistent=_baseline(feedback)
    fixed=[.001533981,.033747577,1.67357304,-.056757289 if preparation else -.072097097,.018407769,3.138524692]
    if cycle_entry:fixed[3]=-.052155347
    if posture_transfer:
        # Use the later 35-second stable observation, not the early in-band
        # completion sample: the actuator advanced one additional count.
        fixed[2]=1.691980809;fixed[3]=-.052155347 if cycle_entry else -.075165059
    if not consistent or any(abs(a-b)>1e-8 for a,b in zip(joints,fixed)):
        raise ValueError('Exact mapping-trial start required')
    root=Path(__file__).resolve().parents[3]
    if preparation:
        # Same wire target as repeated decreasing diagnostic, but a different
        # start. Arrival at its previously observed endpoint is a hypothesis.
        desired=-.064427193;wire=-.07833528577991494
        source='wizard-20260917T191844680352Z-97a90363e07d491a8a62265e011dd43d'
        model_id='REPEATED_DECREASING_ENDPOINT_CYCLE_ENTRY' if cycle_entry else 'LOCAL_START_PREPARATION_HYPOTHESIS'
    else:
        proposal,_=_read(root/'runs/wizard-exports',
            'wizard-20260917T192424925702Z-fd715d4709104bbeb4e274d0d6e83eb1',
            'attachment-wrist-response-map.json')
        model=proposal['model']
        model_id=model['model_sha256']
        if model_id!='cd8e129c18486cf95cadd7799e6a77ed4b1901ab1f630bff4a804e78fa9d73f0':
            raise ValueError('Pinned interpolation model changed')
        desired=-.055;wire=predict_command(model,desired)
        source='wizard-20260917T192424925702Z-fd715d4709104bbeb4e274d0d6e83eb1'
    model=UrdfModel.from_file(root/'models/roarm_m3/roarm_m3_kinematic_40dbd84.urdf')
    origin=modeled_tip(model,joints);sweep=0.;samples=[]
    for i in range(41):
        q=list(joints);q[3]=joints[3]+(wire-joints[3])*i/40
        if i==40:q[3]=wire
        pose=list(forward(*q[:4]));sweep=max(sweep,math.dist(origin,modeled_tip(model,q)))
        if sweep>6 or math.dist(start[:3],pose[:3])>6:raise ValueError('Mapping arc exceeds 6 mm')
        samples.append(dict(joints_rad=q,xyz_pitch=pose))
    c=dict(schema='rocell.wrist_map_trial_candidate.v1',desired_joint_index=3,
        desired_rad=desired,command_rad=wire,baseline_joints_rad=list(joints),
        source_export=source,model_id=model_id,spd=20,acc=1,
        globally_enabled=False,motion_authorized=False)
    if posture_transfer:
        c.update(transfer_experiment='WRIST_TRANSFER_ENTRY_V1' if cycle_entry else 'INCREASING_WRIST_POSTURE_TRANSFER_V1',
                 held_out_validated=False,repeatability_verified=False)
    c['candidate_sha256']=hashlib.sha256(canonical(c)).hexdigest()
    return dict(status='PREVIEW_ONLY_NOT_EXECUTABLE',starting_pose=start,
        target_pose=samples[-1]['xyz_pitch'],target_joints_rad=samples[-1]['joints_rad'],
        samples=samples,hypothetical_tip_sweep_mm=sweep,local_candidate=c,
        compensation_applied=True,motion_authorized=False)
