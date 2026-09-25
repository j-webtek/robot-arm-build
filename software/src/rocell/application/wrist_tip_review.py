"""Offline hypothetical stylus geometry for a completed local wrist cycle.

Reported joints are projected into a vendor model, not measured tip coordinates.
The intermediate arc is interpolated for geometry only, not observed motion.
"""
import math
from .controller_model_baseline import ARM_MAP
from .compensated_elbow_progression import clean_compensated_completion
from .wrist_shared_pair import pair_candidate
from .product_ghost_controller_bridge import bridge_product_ghost
from rocell.geometry import RigidTransform,JointPosition,Vec3


def modeled_tip(model,joints):
    if len(joints)!=6 or any(type(v) not in (int,float) or not math.isfinite(v) for v in joints):
        raise ValueError('Six finite joints required')
    pose=RigidTransform.identity('base_link')
    for value,(_,name) in zip(joints,ARM_MAP):
        pose=pose.compose(model.joint(name).transform_at(JointPosition.radians(value)))
    pose=pose.compose(model.joint('link5_to_hand_tcp').transform_at(None))
    tip=pose.transform_position_mm(Vec3(0,0,-100))
    return [tip.x,tip.y,tip.z]


def review_wrist_tip(reports,ghost_report,model):
    if len(reports)!=2:raise ValueError('One complete two-leg wrist cycle required')
    legs=[];previous=None
    for report,leg in zip(reports,('down','up')):
        run=report.get('run') or {};tx=run.get('transaction') or {}
        if not clean_compensated_completion(run) or tx.get('local_candidate')!=pair_candidate(leg):
            raise ValueError('Clean named wrist leg required')
        start=tx['baseline_joints'];finish=tx['rows'][-1][3]
        if previous is not None and any(abs(a-b)>1e-8 for a,b in zip(start,previous)):
            raise ValueError('Cycle continuity required')
        if any(abs(a-b)>1e-8 for i,(a,b) in enumerate(zip(start,finish)) if i!=3):
            raise ValueError('Wrist-only geometry required')
        arc=[modeled_tip(model,[a+(b-a)*i/40 for a,b in zip(start,finish)]) for i in range(41)]
        delta=[b-a for a,b in zip(arc[0],arc[-1])]
        legs.append(dict(leg=leg,tip_start_mm=arc[0],tip_finish_mm=arc[-1],
            tip_delta_mm=delta,lateral_travel_mm=math.hypot(delta[0],delta[1]),
            vertical_travel_mm=delta[2],wrist_angle_change_deg=math.degrees(finish[3]-start[3]),
            modeled_arc_samples=arc,intermediate_path_observed=False))
        previous=finish
    bridge=bridge_product_ghost(ghost_report)
    entry=bridge['samples'][0]
    first=next((s for s in bridge['samples'] if s['phase']=='HOVER' and s['key']),None)
    if first is None:raise ValueError('Named ghost-key hover required')
    q=[first['solved_arm_joints_rad'][key] for key,_ in ARM_MAP]+[previous[5]]
    ghost_tip=modeled_tip(model,q)
    entry_q=[entry['solved_arm_joints_rad'][key] for key,_ in ARM_MAP]+[previous[5]]
    entry_tip=modeled_tip(model,entry_q)
    return dict(schema='rocell.wrist_hypothetical_tip_review.v2',status='MODEL_GEOMETRY_ONLY',
        frame='VENDOR_BASE_UNREGISTERED',tool_offset_hand_tcp_z_mm=-100,
        joint_mapping_hypothesis='SAME_SIGN_SAME_ZERO_NOT_VALIDATED',legs=legs,
        first_ghost_key=first['key'],first_ghost_phase=first['phase'],first_ghost_tip_mm=ghost_tip,
        route_entry_phase=entry['phase'],route_entry_tip_mm=entry_tip,
        distance_from_cycle_finish_to_route_entry_mm=math.dist(legs[-1]['tip_finish_mm'],entry_tip),
        distance_from_cycle_finish_to_ghost_hover_mm=math.dist(legs[-1]['tip_finish_mm'],ghost_tip),
        modeled_cycle_closure_mm=math.dist(legs[0]['tip_start_mm'],legs[-1]['tip_finish_mm']),
        registered_board_transform=False,physical_accuracy_verified=False,motion_authorized=False,
        contact_authorized=False,keyboard_route_relocated=False,
        limitation='Local arc is not a completed ghost-key approach or measured stylus path.')
