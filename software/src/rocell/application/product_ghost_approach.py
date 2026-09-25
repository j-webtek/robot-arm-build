"""Screen a saved controller pose to the first ghost waypoint, entirely offline."""
import hashlib
import math
from .first_motion_contract import canonical
from .controller_route_preview import _baseline
from .product_ghost_controller_bridge import bridge_product_ghost
from rocell.simulation.controller import ControllerPose, simulate_t104_trace
from rocell.motion.characterization_controller import _screen_reference_trace
from rocell.kinematics.firmware_reference import inverse
from .controller_model_baseline import ARM_MAP
from rocell.geometry import RigidTransform,JointPosition,Vec3


def preview_ghost_approach(source,feedback,*,model=None):
    bridge=bridge_product_ghost(source)
    start,joints,consistent=_baseline(feedback)
    if not consistent: raise ValueError('Feedback/reference mismatch')
    first=bridge['samples'][0]
    target=first['controller_reference_xyz_pitch']
    begin=[*start,joints[4],joints[5]]
    finish=[*target,first['solved_arm_joints_rad']['r'],joints[5]]
    distance=math.dist(begin[:3],finish[:3])
    count=max(1,math.ceil(distance/5),math.ceil(max(abs(a-b) for a,b in zip(begin[3:5],finish[3:5]))/.025))
    result=dict(schema='rocell.product_ghost_approach.v1',status='APPROACH_BUDGET_REJECTED',
        source_bridge_sha256=bridge['report_sha256'],feedback_sha256=hashlib.sha256(canonical(feedback)).hexdigest(),
        starting_controller_pose=begin,target_controller_pose=finish,target_key=first['key'],
        target_phase=first['phase'],translation_mm=distance,planned_legs=count,legs=[],
        tool_selection=bridge['tool_selection'],gripper_preserved_rad=joints[5],
        motion_authorized=False,hardware_access=False,physical_accuracy_verified=False,
        full_arm_clearance_verified=False,compensation_applied=False,
        limitation='Hypothetical joint/frame correspondence; no installed tip transform or collision qualification.')
    if count>64: return result
    previous=begin
    joint_start=list(joints[:5])
    joint_min=list(joint_start); joint_max=list(joint_start)
    previous_joint=list(joint_start)
    # Provisional simulation limits, not verified installed mechanical stops.
    bounds=((-math.pi,math.pi),(-math.pi/2,math.pi/2),(0,2.95),(-math.pi/2,math.pi/2),(-math.pi,math.pi))
    max_jump=0.
    tip_min=[math.inf]*3; tip_max=[-math.inf]*3; tip_first=None; tip_last=None
    for i in range(1,count+1):
        goal=[a+(b-a)*i/count for a,b in zip(begin,finish)]
        try:
            trace=simulate_t104_trace(ControllerPose(*previous),ControllerPose(*goal),spd_coefficient=.05,maximum_samples=1024)
            check=_screen_reference_trace(trace)
            row=dict(index=i-1,target=goal,status=check['status'],sample_count=len(trace.samples))
            for sample in trace.samples:
                p=sample.pose
                solved=[*inverse(p.x_mm,p.y_mm,p.z_mm,p.pitch_rad),p.roll_rad]
                max_jump=max(max_jump,max(abs(a-b) for a,b in zip(previous_joint,solved)))
                for j,value in enumerate(solved):
                    joint_min[j]=min(joint_min[j],value); joint_max[j]=max(joint_max[j],value)
                if not all(lo<=value<=hi for value,(lo,hi) in zip(solved,bounds)):
                    row['status']='PROVISIONAL_JOINT_LIMIT_REJECTED'; break
                previous_joint=solved
                if model is not None:
                    pose=RigidTransform.identity('base_link')
                    for value,(_,name) in zip(solved,ARM_MAP):
                        pose=pose.compose(model.joint(name).transform_at(JointPosition.radians(value)))
                    pose=pose.compose(model.joint('link5_to_hand_tcp').transform_at(None))
                    tip=pose.transform_position_mm(Vec3(0,0,-100))
                    xyz=[tip.x,tip.y,tip.z]
                    if tip_first is None: tip_first=xyz
                    tip_last=xyz
                    tip_min=[min(a,b) for a,b in zip(tip_min,xyz)]
                    tip_max=[max(a,b) for a,b in zip(tip_max,xyz)]
            row['target_joints_rad']=[*inverse(*goal[:4]),goal[4]]
            row['joint_delta_from_start_deg']=[math.degrees(v-joint_start[j]) for j,v in enumerate(row['target_joints_rad'])]
        except (ValueError,OverflowError):
            row=dict(index=i-1,target=goal,status='TRACE_UNAVAILABLE',sample_count=0)
        result['legs'].append(row)
        result['joint_review']=dict(joint_order=['base','shoulder','elbow','wrist_pitch','wrist_roll'],
            minimum_rad=joint_min,maximum_rad=joint_max,
            maximum_excursion_deg=[math.degrees(max(abs(lo-v),abs(hi-v))) for lo,hi,v in zip(joint_min,joint_max,joint_start)],
            maximum_adjacent_sample_change_deg=math.degrees(max_jump),
            installed_limits_verified=False,tool_sweep_verified=False)
        if tip_first is not None:
            result['hypothetical_tip_sweep']=dict(frame='VENDOR_BASE_UNREGISTERED',
                offset_hand_tcp_z_mm=-100,minimum_mm=tip_min,maximum_mm=tip_max,
                first_mm=tip_first,last_mm=tip_last,physical_clearance_verified=False,
                same_sign_zero_joint_mapping_assumed=True)
        if row['status']!='REFERENCE_IK_PASS':
            result['status']='APPROACH_REFERENCE_REJECTED'; return result
        previous=goal
    result['status']='APPROACH_REFERENCE_PASS_NOT_EXECUTABLE'
    return result
