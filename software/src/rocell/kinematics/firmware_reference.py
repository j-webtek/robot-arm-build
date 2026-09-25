"""Pinned firmware equations, not installed calibration or motion authority.

Transcribed from RoArm-M3_config.h:101-177 and RoArm-M3_module.h:531-555,
595-619,694-731 in the archive below. The Cartesian FK omits l1, uses
the configured end edge, and does not depend on roll or gripper angles.
"""
import math

REFERENCE_SHA256 = 'a28247fee0bbb65cc034ff206031b8700d2b1ec8e3a1fa4b1a5a7365c55f1a57'
REFERENCE_URL = 'https://files.waveshare.com/wiki/RoArm-M3/RoArm-M3_example_20260701.zip'
L2, T2 = math.hypot(236.82, 30), math.atan2(30, 236.82)
L3 = 144.49
LE, TE = math.hypot(171.67, 13.69), math.atan2(13.69, 171.67)


def _finite(values):
    if any(type(v) not in (int,float) or not math.isfinite(v) for v in values):
        raise ValueError('Finite numerical reference inputs required')


def forward(base, shoulder, elbow, wrist):
    """Reference R_ctrl XYZ/pitch; no base height or installed stylus offset."""
    _finite((base,shoulder,elbow,wrist))
    parts = ((L2, math.pi/2-shoulder-T2),
             (L3, math.pi/2-elbow-shoulder),
             (LE, math.pi/2-elbow-shoulder-wrist-TE))
    radius = sum(length*math.cos(angle) for length,angle in parts)
    z = sum(length*math.sin(angle) for length,angle in parts)
    return (radius*math.cos(base), radius*math.sin(base), z,
            elbow+shoulder+wrist-math.pi/2)


def inverse(x, y, z, pitch):
    """Positive-radius regular branch only; reject domain errors, never clamp."""
    _finite((x,y,z,pitch))
    dx = -LE*math.cos(TE+pitch-math.pi)
    dy = -LE*math.sin(TE+pitch-math.pi)
    radius = math.hypot(x,y)-dx
    height = z+dy
    if radius <= 1e-6 or abs(height) < 1e-6:
        raise ValueError('This offline review covers only the regular bench branch')
    distance = math.hypot(radius,height)
    psi = math.acos((L2*L2+distance*distance-L3*L3)/(2*L2*distance))+T2
    shoulder = math.pi/2-math.atan2(height,radius)-psi
    elbow = psi+math.acos((L3*L3+distance*distance-L2*L2)/(2*distance*L3))
    wrist = math.pi/2-shoulder-elbow+pitch
    return math.atan2(y,x), shoulder, elbow, wrist


def servo_goals(joints):
    """Pinned jointCtrlRad count conversion, including clamps and 2047 midpoint.

    Module lines 306-398; config lines 94/96. These are predicted bus targets,
    not captured serial-bus writes or proof of the installed firmware version.
    """
    if len(joints)!=6:
        raise ValueError('Six logical joints required')
    _finite(joints)
    def clip(v,lo,hi):return min(hi,max(lo,v))
    def ticks(v):
        value=v*4096/(2*math.pi)
        # C++ round is half away from zero, unlike Python round.
        return math.floor(value+.5) if value>=0 else math.ceil(value-.5)
    b,s,e,t,r,g=joints
    shoulder=ticks(clip(s,-math.pi/2,math.pi/2))
    return dict(b=2047+ticks(-clip(b,-math.pi,math.pi)),s=2047+shoulder,
        s_follower=2047-shoulder,e=clip(ticks(e)+1024,1024,3071),
        t=2047+ticks(clip(t,-math.pi/2,math.pi/2)),
        r=2047-ticks(clip(r,-math.pi,math.pi)),g=clip(ticks(g),700,3396))


def feedback_counts(joints):
    """Reconstruct counts from reported angles using module lines 42-62."""
    if len(joints)!=6:
        raise ValueError('Six logical joints required')
    _finite(joints)
    b,s,e,t,r,g=joints
    scale=4096/(2*math.pi)
    return dict(zip(('b','s','e','t','r','g'),
        (round(2048-b*scale),round(2048+s*scale),round(1024+e*scale),
         round(2048+t*scale),round(2048-r*scale),round(g*scale))))


def joint_response_comparison(baseline, expected, reported, *, commanded_joints=('b','s','e','t','r','g')):
    """Separate ideal angle errors from predicted bus-target count errors."""
    start=feedback_counts(baseline)
    target=servo_goals(expected)
    actual=feedback_counts(reported)
    if type(commanded_joints) is not tuple or any(k not in start for k in commanded_joints):
        raise ValueError('Explicit known commanded joints required')
    return [dict(joint=k,commanded=k in commanded_joints,baseline_rad=a,ideal_target_rad=b,reported_rad=c,
        ideal_delta_deg=math.degrees(b-a),reported_delta_deg=math.degrees(c-a),
        ideal_error_rad=c-b,baseline_reconstructed_count=start[k],
        predicted_goal_count=target[k] if k in commanded_joints else None,reported_reconstructed_count=actual[k],
        predicted_count_change=target[k]-start[k] if k in commanded_joints else None,
        reported_count_change=actual[k]-start[k],count_error=actual[k]-target[k] if k in commanded_joints else None)
        for k,a,b,c in zip(('b','s','e','t','r','g'),baseline,expected,reported)]
