"""Offline frame comparison under an explicit, unqualified joint-map hypothesis.

Controller FK and URDF FK are not independent physical measurements. This
diagnostic never estimates a calibration from one pose or authorizes motion.
"""
import math
from rocell.geometry import JointPosition, RigidTransform
from rocell.kinematics.firmware_reference import forward, REFERENCE_SHA256


ARM_MAP = (('b','base_link_to_link1'), ('s','link1_to_link2'),
           ('e','link2_to_link3'), ('t','link3_to_link4'), ('r','link4_to_link5'))


def compare_controller_model(report, model):
    if report.get('status') != 'SUCCEEDED' or not report.get('identity_before_matched') or not report.get('identity_after_matched'):
        raise ValueError('Successful identity-matched feedback required')
    joints = report['joints_rad']
    pose = RigidTransform.identity('world')
    pose = pose.compose(model.joint('world_to_base_link').transform_at(None))
    base = pose
    # The gripper is a sibling branch of hand_tcp, not an ancestor. Do not
    # replace its reported value or treat it as part of the tool transform.
    for key, name in ARM_MAP:
        value = joints[key]
        if type(value) not in (int,float) or not math.isfinite(value):
            raise ValueError('Finite reported arm joints required')
        pose = pose.compose(model.joint(name).transform_at(JointPosition.radians(value)))
    pose = pose.compose(model.joint('link5_to_hand_tcp').transform_at(None))
    local = base.inverse().compose(pose)
    def xyz(transform):
        point = transform.translation_mm
        return [point.x, point.y, point.z]
    cart = report.get('controller_cartesian') or {}
    values = cart.get('values') or {}
    observed = [values.get(key) for key in ('x','y','z')]
    complete = all(type(v) in (int,float) and math.isfinite(v) for v in observed)
    reference = forward(*(joints[key] for key in ('b','s','e','t')))
    return dict(schema='rocell.controller_model_baseline.v1',
        hypothesis='SAME_SIGN_SAME_ZERO_REPORTED_ARM_JOINTS_NOT_VALIDATED',
        joint_map=dict(ARM_MAP), reported_joints_rad=dict(joints),
        controller_xyz_mm=observed, controller_pitch_rad=values.get('tit'),
        vendor_world_hand_tcp_mm=xyz(pose), vendor_base_hand_tcp_mm=xyz(local),
        firmware_reference=dict(archive_sha256=REFERENCE_SHA256,
            predicted_xyz_mm=list(reference[:3]), predicted_pitch_rad=reference[3],
            position_residual_mm=math.dist(observed,reference[:3]) if complete else None,
            endpoint='CONFIGURED_FIRMWARE_END_EDGE_NOT_INSTALLED_STYLUS',
            includes_base_height=False, installed_binary_verified=False,
            physical_accuracy_verified=False),
        hypothetical_frame_equivalence_residual_mm=None if not complete else {
            frame: [predicted[i]-observed[i] for i in range(3)]
            for frame,predicted in [('vendor_world',xyz(pose)),('vendor_base',xyz(local))]},
        gripper_used_for_hand_tcp=False, installed_tool_offset_applied=False,
        controller_model_correlation_verified=False, physical_accuracy_verified=False,
        calibration_produced=False, motion_authorized=False,
        interpretation='Residuals assume frame equivalence solely to test that hypothesis; never use them as a correction offset.')
