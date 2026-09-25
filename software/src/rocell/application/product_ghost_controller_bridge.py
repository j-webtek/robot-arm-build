"""Offline URDF-joint to firmware-reference route under an explicit hypothesis.

Never pass board XYZ directly to firmware. Reuse solved joints to project the
configured firmware end edge, retaining the different desired virtual tip frame.
This is not an installed-controller calibration or a native execution request.
"""
import hashlib
import math
from .first_motion_contract import canonical
from .controller_model_baseline import ARM_MAP
from rocell.kinematics.firmware_reference import forward, inverse, REFERENCE_SHA256


def bridge_product_ghost(report):
    route=(report.get('dense_route') or {}).get('round') or {}
    rows=route.get('joint_results')
    if (report.get('schema')!='rocell.static_task_rehearsal.v1'
            or report.get('status')!='DENSE_SAMPLES_PASS_NOT_EXECUTABLE'
            or report.get('device')!='keyboard' or report.get('physical_authority') is not False
            or report.get('tool_selection',{}).get('hand_tcp_to_tip_z_mm')!=-100
            or route.get('all_waypoints_accepted') is not True
            or type(rows) is not list or not 2<=len(rows)<=128
            or route.get('waypoint_count')!=len(rows)
            or route.get('evaluated_waypoint_count')!=len(rows)):
        raise ValueError('Complete passing fixed-100-mm keyboard route required')
    samples=[]
    for index,row in enumerate(rows):
        if row.get('accepted') is not True or row.get('waypoint_sequence')!=index:
            raise ValueError('Accepted contiguous route samples required')
        values=row.get('solution_arm_joint_positions_rad') or {}
        joints=[values.get(name) for _,name in ARM_MAP]
        if any(type(v) not in (int,float) or not math.isfinite(v) for v in joints):
            raise ValueError('Complete finite joint solution required')
        reference=forward(*joints[:4])
        recovered=inverse(*reference)
        residual=max(abs(a-b) for a,b in zip(joints,recovered))
        if residual>1e-6:
            raise ValueError('Firmware inverse branch differs from solved joint hypothesis')
        samples.append(dict(sequence=index,key=row.get('semantic_target'),phase=row.get('phase'),
            action_index=row.get('action_index'),
            achieved_virtual_tip_board_mm=row.get('achieved_tip_position_board_mm'),
            solved_arm_joints_rad=dict(zip((key for key,_ in ARM_MAP),joints)),
            controller_reference_xyz_pitch=list(reference),inverse_roundtrip_rad=residual))
    legs=[dict(sequence=i,start_sequence=i,target_sequence=i+1,
               start_reference=a['controller_reference_xyz_pitch'],
               target_reference=b['controller_reference_xyz_pitch'],
               translation_mm=math.dist(a['controller_reference_xyz_pitch'][:3],
                                        b['controller_reference_xyz_pitch'][:3]))
          for i,(a,b) in enumerate(zip(samples,samples[1:]))]
    result=dict(schema='rocell.product_ghost_controller_bridge.v1',status='HYPOTHETICAL_REFERENCE_ROUTE_ONLY',
        hypothesis='SAME_SIGN_SAME_ZERO_REPORTED_ARM_JOINTS_NOT_VALIDATED',
        source_report_sha256=hashlib.sha256(canonical(report)).hexdigest(),
        source_plan_hash=report['plan_hash'],source_hashes=report['source_hashes'],
        tool_selection=report['tool_selection'],keyboard_placement_overlay=report.get('keyboard_placement_overlay'),
        reference_sha256=REFERENCE_SHA256,samples=samples,legs=legs,
        maximum_inverse_roundtrip_rad=max(s['inverse_roundtrip_rad'] for s in samples),
        maximum_adjacent_translation_mm=max(l['translation_mm'] for l in legs),
        approach_from_live_pose_included=False,controller_model_correlation_verified=False,
        full_arm_clearance_verified=False,physical_accuracy_verified=False,
        motion_authorized=False,hardware_commands_generated=0,hardware_access=False,
        limitations=['Firmware end-edge positions are not board coordinates or installed stylus-tip positions.',
            'Point roundtrips do not qualify interpolation between samples, speed or live approach.',
            'No gripper goal is invented; native execution must preserve a fresh measured state.',
            'Same-sign/zero joint correspondence remains an explicit unvalidated hypothesis.'])
    return dict(result,report_sha256=hashlib.sha256(canonical(result)).hexdigest())
