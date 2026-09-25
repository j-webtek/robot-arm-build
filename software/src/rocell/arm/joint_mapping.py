"""Pinned RoArm-M3 reference joint map; analysis/preview, never native admission.

Firmware register conversion is NOT an empirical compensation model. Do not
substitute a predicted feedback angle for a transmitted command angle.
"""
from dataclasses import dataclass, asdict
import math

REFERENCE_URL='https://files.waveshare.com/wiki/RoArm-M3/RoArm-M3_example_20260701.zip'
REFERENCE_SHA256='a28247fee0bbb65cc034ff206031b8700d2b1ec8e3a1fa4b1a5a7365c55f1a57'
STEP_RAD=2*math.pi/4096


@dataclass(frozen=True)
class JointMapping:
    key: str
    name: str
    command_id: int
    telemetry_index: int
    servo_ids: tuple
    register_sign: int
    register_offset: int
    feedback_offset: int


# IDs are logical T101 joint IDs, not servo bus IDs. Shoulder has two servos
# but one reported angle; its feedback is from the driving servo only.
JOINT_MAP=(
    JointMapping('b','base',1,0,(11,),-1,2047,2048),
    JointMapping('s','shoulder',2,1,(12,13),1,2047,2048),
    JointMapping('e','elbow',3,2,(14,),1,1024,1024),
    JointMapping('t','wrist_pitch',4,3,(15,),1,2047,2048),
    JointMapping('r','wrist_roll',5,4,(16,),-1,2047,2048),
    JointMapping('g','gripper',6,5,(17,),1,0,0),
)


def mapping_for(key):
    if type(key) is not str:
        raise ValueError('Exact telemetry joint key required')
    for joint in JOINT_MAP:
        if joint.key==key:return joint
    raise ValueError('Unknown joint key')


def _finite(value):
    if type(value) not in (int,float) or not math.isfinite(value) or abs(value)>2*math.pi:
        raise ValueError('Finite bounded radian angle required')
    return value


def reference_joint_goal(key, target_rad):
    """Mirror reference rounding/clamping, not installed-firmware attestation.

    Source: config lines 61–67, 86–96; module lines 36–62, 306–403,
    635–661 and 770–797. Register limits are not qualified physical limits.
    """
    joint=mapping_for(key);requested=_finite(target_rad);limited=requested
    if key in ('b','r'):limited=min(math.pi,max(-math.pi,requested))
    if key in ('s','t'):limited=min(math.pi/2,max(-math.pi/2,requested))
    value=limited/STEP_RAD
    steps=int(math.copysign(math.floor(abs(value)+.5),value))
    raw_goal=joint.register_offset+joint.register_sign*steps
    goal=raw_goal
    if key=='e':goal=min(3071,max(1024,goal))
    if key=='g':goal=min(3396,max(700,goal))
    registers=[goal]
    if key=='s':registers.append(2047-steps)
    feedback=joint.register_sign*(goal-joint.feedback_offset)*STEP_RAD
    return dict(schema='rocell.reference_joint_goal.v1',joint=key,
        source_sha256=REFERENCE_SHA256,requested_rad=requested,
        logical_joint_id=joint.command_id,servo_ids=list(joint.servo_ids),
        goal_registers=registers,predicted_feedback_rad=feedback,
        clamped=limited!=requested or goal!=raw_goal,
        registers_in_wire_range=all(0<=p<=4095 for p in registers),
        reference_feedback_error_rad=feedback-requested,
        installed_firmware_verified=False,motion_authorized=False)


def preview_mapping_probe(key, *, start_rad, delta_deg):
    """One uncorrected local mapping probe, for simulation/review only.

    Does not accept correction offsets, widen native wrist permits, or certify
    swept clearance. All six starting coordinates remain in the preview.
    """
    joint=mapping_for(key)
    if type(start_rad) not in (list,tuple) or len(start_rad)!=6:
        raise ValueError('Six reported starting angles required')
    for angle in start_rad:_finite(angle)
    if type(delta_deg) not in (int,float) or not math.isfinite(delta_deg) or not .5<abs(delta_deg)<=2:
        raise ValueError('Local probe delta must exceed 0.5 and not exceed 2 degrees')
    target=start_rad[joint.telemetry_index]+math.radians(delta_deg)
    goal=reference_joint_goal(key,target)
    if goal['clamped'] or not goal['registers_in_wire_range']:
        raise ValueError('Probe would clamp or exceed reference register range')
    return dict(schema='rocell.joint_mapping_probe_preview.v1',joint=asdict(joint),
        start_joints_rad=list(start_rad),nominal_target_rad=target,
        candidate_command=dict(T=101,joint=joint.command_id,rad=target,spd=20,acc=1),
        reference_prediction=goal,maximum_commands=1,automatic_retry=False,
        compensation_applied=False,motion_authorized=False,
        selected_joint_native_admission_required=True,physical_clearance_verified=False)
