"""Named first 5 mm approach diagnostic; not authority for the full ghost route."""
import math
from .controller_route_preview import _baseline
from rocell.kinematics.firmware_reference import inverse
from rocell.simulation.controller import ControllerPose,simulate_t104_trace
from rocell.motion.characterization_controller import _screen_reference_trace

# PARK entry projected from the reviewed full-size keyboard route, not key hover. This is a
# firmware-reference endpoint, NOT a registered board point or mounted stylus tip.
ANCHOR=(419.52610416744125,-15.089324125038159,49.47971128648259,3.4396120414115217e-6)
SOURCE='wizard-20260917T170817165722Z-9dd8fd21d5d54d038c97d6ec01d64042'


def preview_first_step(feedback, *, post_wrist=False):
    if type(post_wrist) is not bool:
        raise ValueError('Explicit posture selection required')
    start,joints,consistent=_baseline(feedback)
    fixed=(.001533981,0,None,.053689328,.01994175,3.138524692)
    if post_wrist:
        # New experiment scope, not a widening or replay of the original start.
        # Three read-only observations at 17:35 UTC agree on this settled roll;
        # preserve it rather than issuing a roll correction or widening scope.
        fixed=(.001533981,.007669904,1.563126423,.007669904,.018407769,3.138524692)
    matches=(all(abs(v-fixed[i])<=1e-8 for i,v in enumerate(joints)) if post_wrist else
             1.520<=joints[2]<=1.540 and all(abs(v-fixed[i])<=1e-8 for i,v in enumerate(joints) if i!=2))
    if not consistent or not matches:
        raise ValueError('Reviewed local starting posture required')
    distance=math.dist(start[:3],ANCHOR[:3]); fraction=5/distance
    if not 150<=distance<=220: raise ValueError('Unexpected approach geometry')
    target=[a+(b-a)*fraction for a,b in zip(start,ANCHOR)]
    trace=simulate_t104_trace(ControllerPose(*start,*joints[4:]),ControllerPose(*target,*joints[4:]),
                             spd_coefficient=.05,maximum_samples=1024)
    check=_screen_reference_trace(trace)
    if check['status']!='REFERENCE_IK_PASS': raise ValueError('Reference path failed')
    bounds=((-math.pi,math.pi),(-math.pi/2,math.pi/2),(0,2.95),(-math.pi/2,math.pi/2))
    for sample in trace.samples:
        p=sample.pose; solved=inverse(p.x_mm,p.y_mm,p.z_mm,p.pitch_rad)
        if (max(abs(a-b) for a,b in zip(solved,joints[:4]))>math.radians(3)
                or not all(lo<=v<=hi for v,(lo,hi) in zip(solved,bounds))):
            raise ValueError('First-step joint envelope failed')
    return dict(status='PREVIEW_ONLY_NOT_EXECUTABLE',starting_pose=start,target_pose=target,
        experiment='POST_WRIST_GHOST_APPROACH_5MM_V2' if post_wrist else 'FIRST_GHOST_APPROACH_5MM_V1',
        target_joints_rad=[*inverse(*target),*joints[4:]],source_export=SOURCE,
        translation_mm=5,sample_count=len(trace.samples),motion_authorized=False,
        tool_clearance_verified=False,compensation_applied=False)
