"""Offline T104 reference-path screening for the local hypothetical tip cycle.

Projection uses solved joints, never passes URDF tip coordinates as firmware XYZ.
No transport is imported and no executable command or motion authority is issued.
"""
import math

from .controller_model_baseline import ARM_MAP
from .local_tip_cycle import preview_local_tip_cycle
from .wrist_tip_review import modeled_tip
from rocell.kinematics.firmware_reference import forward, inverse, REFERENCE_SHA256
from rocell.simulation.controller import (
    ControllerPose, ControllerJointState, simulate_t104_trace,
    validate_provisional_simulation_intersection,
)


def preview_local_tip_controller(model, joints, *, direction='press'):
    reference = preview_local_tip_cycle(model, joints, direction=direction)
    result = dict(schema='rocell.local_tip_controller_preview.v1',
                  status='LOCAL_REFERENCE_REJECTED', local_reference=reference,
                  firmware_reference_sha256=REFERENCE_SHA256, legs=[],
                  motion_authorized=False, hardware_commands_generated=0,
                  physical_accuracy_verified=False, full_arm_clearance_verified=False,
                  compensation_applied=False, installed_firmware_verified=False,
                  speed_coefficient=.05)
    if reference['status'] != 'LOCAL_TIP_REFERENCE_PASS_NOT_EXECUTABLE':
        return result
    origin = reference['start_tip_mm']
    waypoints = reference['waypoints']
    # Expose scale relative to the nominal 4096-count angle increment. This is
    # not a prediction of firmware rounding, deadband, or actual servo motion.
    angle_step=2*math.pi/4096
    result['joint_motion_demands']=[]
    for label,a,b in (('PRESS' if direction=='press' else 'RETRACT',waypoints[0],waypoints[4]),
                      ('RETRACT' if direction=='press' else 'PRESS',waypoints[4],waypoints[-1])):
        result['joint_motion_demands'].append(dict(phase=label,
            joints=[dict(joint=name,delta_rad=y-x,delta_deg=math.degrees(y-x),
                nominal_encoder_steps=(y-x)/angle_step,
                direction='UNCHANGED' if abs(y-x)<1e-7 else 'INCREASING' if y>x else 'DECREASING')
                for name,x,y in zip(('base','shoulder','elbow','wrist_pitch','wrist_roll','gripper'),
                                    a['joints_rad'],b['joints_rad'])]))
    result['nominal_encoder_steps_are_not_servo_response_predictions']=True
    max_lateral = max_vertical = max_excursion = 0.
    try:
        poses = []
        for row in waypoints:
            q = row['joints_rad']
            xyz_pitch = forward(*q[:4])
            if max(abs(a-b) for a,b in zip(inverse(*xyz_pitch), q[:4])) > 1e-6:
                raise ValueError('Firmware inverse branch differs from desired joints')
            poses.append(ControllerPose(*xyz_pitch, q[4], q[5]))
        # Screen each controller interpolation, including its explicit terminal
        # target. These are model samples, not observations from the real arm.
        for index, (start, target) in enumerate(zip(poses, poses[1:])):
            trace = simulate_t104_trace(start, target, spd_coefficient=.05,
                                        maximum_samples=1024)
            samples = []
            for sample in trace.samples:
                p = sample.pose
                q = [*inverse(p.x_mm,p.y_mm,p.z_mm,p.pitch_rad),
                     p.roll_rad,p.gripper_raw_rad]
                validate_provisional_simulation_intersection(ControllerJointState(*q))
                for value, (_, name) in zip(q, ARM_MAP):
                    limit = model.joint(name).limit
                    if not limit.lower.value <= value <= limit.upper.value:
                        raise ValueError('URDF joint limit exceeded')
                tip = modeled_tip(model,q)
                fraction = sample.cosine_eased_fraction
                expected_z = (waypoints[index]['tip_mm'][2] + fraction *
                              (waypoints[index+1]['tip_mm'][2]-waypoints[index]['tip_mm'][2]))
                max_lateral = max(max_lateral,math.hypot(tip[0]-origin[0],tip[1]-origin[1]))
                max_vertical = max(max_vertical,abs(tip[2]-expected_z))
                max_excursion = max(max_excursion,max(abs(a-b) for a,b in zip(q[:5],joints[:5])))
                samples.append(dict(fraction=fraction,joints_rad=q,tip_mm=tip))
            result['legs'].append(dict(index=index,start=start.to_dict(),
                                      target=target.to_dict(),samples=samples))
    except (ValueError,OverflowError,ZeroDivisionError) as exc:
        result.update(status='CONTROLLER_REFERENCE_REJECTED',reason=str(exc))
        return result
    result.update(maximum_lateral_drift_mm=max_lateral,
                  maximum_vertical_interpolation_error_mm=max_vertical,
                  maximum_joint_excursion_deg=math.degrees(max_excursion),
                  status='CONTROLLER_REFERENCE_PASS_NOT_EXECUTABLE'
                  if max_lateral<=.05 and max_vertical<=.02 and max_excursion<=math.radians(3)
                  else 'CONTROLLER_REFERENCE_REJECTED')
    return result
