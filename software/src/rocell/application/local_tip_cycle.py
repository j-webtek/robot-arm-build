"""Simulation-only 2 mm vertical tip cycle retaining the current tool axis.

The local task frame is synthetic, not a registered board or keyboard placement.
No wire commands or compensation are generated here.
"""
import math
from .controller_model_baseline import ARM_MAP
from .wrist_tip_review import modeled_tip
from rocell.geometry import RigidTransform,JointPosition,Vec3
from rocell.models.frames import Point3Mm
from rocell.kinematics.ik import RoArmM3NumericalIk,IkOptions,BoardToolTipTarget


def preview_local_tip_cycle(model,joints, *, direction='press'):
    if direction not in ('press','retract'):
        raise ValueError('Named press or retract direction required')
    sign=1 if direction=='press' else -1
    origin=modeled_tip(model,joints)  # Validates finite six-joint input.
    world_T_base=model.joint('world_to_base_link').transform_at(None)
    hand=world_T_base
    for value,(_,name) in zip(joints,ARM_MAP):
        hand=hand.compose(model.joint(name).transform_at(JointPosition.radians(value)))
    hand=hand.compose(model.joint('link5_to_hand_tcp').transform_at(None))
    world_origin=world_T_base.transform_position_mm(Vec3(*origin))
    # Align the solver's required +Z tool axis to the existing tool orientation,
    # without pretending the tool is perpendicular to an installed keyboard.
    world_T_local=RigidTransform('world','local_tip_preview',hand.rotation,world_origin)
    local_T_world=world_T_local.inverse()
    seed={name:JointPosition.radians(value) for value,(_,name) in zip(joints,ARM_MAP)}
    bounds={name:(max(model.joint(name).limit.lower.value,value-math.radians(3)),
                  min(model.joint(name).limit.upper.value,value+math.radians(3)))
            for value,(_,name) in zip(joints,ARM_MAP)}
    solver=RoArmM3NumericalIk(model=model,board_T_world=local_T_world,
        hand_tcp_to_tip_z_mm=-100,fixed_gripper_position=JointPosition.radians(.2),
        ready_arm_joint_positions=seed,joint_bounds_rad=bounds,
        options=IkOptions(max_attempts=2,max_iterations_per_attempt=100,
                          position_tolerance_mm=.02,alignment_tolerance_rad=.0005))
    result=dict(schema='rocell.local_tip_cycle_preview.v2',status='IK_REJECTED',
        frame='VENDOR_BASE_UNREGISTERED',tool_offset_hand_tcp_z_mm=-100,
        fixed_model_gripper_is_placeholder=True,controller_gripper_preserved_rad=joints[5],
        start_tip_mm=origin,depth_mm=2,direction=direction,waypoints=[],hardware_commands_generated=0,
        motion_authorized=False,physical_accuracy_verified=False,keyboard_route_relocated=False,
        tool_axis_held_at_start=True,tool_axis_normal_to_keyboard_verified=False,
        full_arm_clearance_verified=False,
        interpolation_model='LINEAR_JOINT_REFERENCE_NOT_FIRMWARE_TRAJECTORY',
        joint_mapping_hypothesis='SAME_SIGN_SAME_ZERO_NOT_VALIDATED')
    down=[list(joints)]
    for step in range(1,5):
        goal=Vec3(origin[0],origin[1],origin[2]-sign*.5*step)
        world_goal=world_T_base.transform_position_mm(goal)
        local_goal=local_T_world.transform_position_mm(world_goal)
        solved=solver.solve(BoardToolTipTarget(Point3Mm('local_tip_preview',local_goal.x,local_goal.y,local_goal.z)),
                            seed_joint_positions=(seed,))
        if not solved.solution_arm_joint_positions:return result
        seed={p.name:p.position for p in solved.solution_arm_joint_positions}
        down.append([seed[name].value for _,name in ARM_MAP]+[joints[5]])
    route=down+down[-2::-1]
    max_lateral=0.;max_excursion=0.;max_vertical_error=0.;samples=0
    # Compare every interpolated point against the requested vertical line,
    # not merely against an IK solver's success flag or the final return pose.
    requested_depths=[sign*d for d in (0,.5,1,1.5,2,1.5,1,.5,0)]
    for index,q in enumerate(route):
        tip=modeled_tip(model,q)
        phase=direction.upper() if index<=4 else ('RETRACT' if direction=='press' else 'PRESS')
        result['waypoints'].append(dict(index=index,phase=phase,
            joints_rad=q,tip_mm=tip))
    for segment,(a,b) in enumerate(zip(route,route[1:])):
        for i in range(21):
            q=[x+(y-x)*i/20 for x,y in zip(a,b)];tip=modeled_tip(model,q);samples+=1
            max_lateral=max(max_lateral,math.hypot(tip[0]-origin[0],tip[1]-origin[1]))
            depth=requested_depths[segment]+(requested_depths[segment+1]-requested_depths[segment])*i/20
            max_vertical_error=max(max_vertical_error,abs(tip[2]-(origin[2]-depth)))
            max_excursion=max(max_excursion,max(abs(x-y) for x,y in zip(q[:5],joints[:5])))
    result.update(status='LOCAL_TIP_REFERENCE_PASS_NOT_EXECUTABLE' if max_lateral<=.05 and max_vertical_error<=.02 and max_excursion<=math.radians(3) else 'PATH_REJECTED',
        maximum_vertical_tracking_error_mm=max_vertical_error,
        maximum_lateral_drift_mm=max_lateral,maximum_joint_excursion_deg=math.degrees(max_excursion),
        interpolated_samples=samples,modeled_return_error_mm=math.dist(modeled_tip(model,route[-1]),origin))
    return result
