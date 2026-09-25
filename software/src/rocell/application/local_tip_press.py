"""One named uncompensated 2 mm hypothetical tip press; no return or contact.

The frozen goal comes from the reviewed local-tip export, not a registered key.
Every call screens the direct T104 path rather than assuming the eight-segment
offline cycle qualifies this single command.
"""
import math
from pathlib import Path
from .controller_route_preview import _baseline
from .wrist_tip_review import modeled_tip
from rocell.geometry import UrdfModel
from rocell.kinematics.firmware_reference import forward,inverse
from rocell.simulation.controller import ControllerPose,simulate_t104_trace
from rocell.motion.characterization_controller import _screen_reference_trace

START=(.001533981,.033747577,1.636757501,-.052155347,.018407769,3.138524692)
GOAL=(.0015339803487479952,.03463726699136274,1.6495405316850362,-.06582603838648644)
SOURCE='wizard-20260917T182339455535Z-be6764567ff04c50a55c22152b11366a'
RETRACT_START=(.001533981,.033747577,1.670505078,-.064427193,.018407769,3.138524692)
RETRACT_GOAL=(.0015339816533875908,.03268444235256817,1.6579063063032675,-.05076729459839498)
RETRACT_SOURCE='wizard-20260917T183226443418Z-6e2e08653f384b7e8bb28ac538501793'


def preview_local_tip_press(feedback, *, retract=False, post_transfer=False):
    if type(retract) is not bool:raise ValueError('Explicit direction required')
    if type(post_transfer) is not bool or (post_transfer and retract):raise ValueError('Exclusive post-transfer press required')
    reference_start=RETRACT_START if retract else START
    goal=RETRACT_GOAL if retract else GOAL
    if post_transfer:
        # Frozen endpoint from the verified-hold controller-reference preview.
        reference_start=(.001533981,.033747577,1.691980809,-.052155347,.018407769,3.138524692)
        goal=(.0015339803420119486,.03509433335332164,1.7042865196488426,-.06580586570901861)
    vertical_delta=2 if retract else -2
    start,joints,consistent=_baseline(feedback)
    if not consistent or any(abs(a-b)>1e-8 for a,b in zip(joints,reference_start)):
        raise ValueError('Reviewed local-tip starting posture required')
    target=forward(*goal)
    trace=simulate_t104_trace(ControllerPose(*start,*joints[4:]),
        ControllerPose(*target,*joints[4:]),spd_coefficient=.05,maximum_samples=1024)
    if _screen_reference_trace(trace)['status']!='REFERENCE_IK_PASS':
        raise ValueError('Direct controller path failed')
    model=UrdfModel.from_file(Path(__file__).resolve().parents[3]/'models/roarm_m3/roarm_m3_kinematic_40dbd84.urdf')
    origin=modeled_tip(model,joints)
    max_lateral=max_vertical=0.
    for sample in trace.samples:
        p=sample.pose
        solved=[*inverse(p.x_mm,p.y_mm,p.z_mm,p.pitch_rad),*joints[4:]]
        if max(abs(a-b) for a,b in zip(solved,joints))>math.radians(3):
            raise ValueError('Direct press exceeds joint excursion')
        tip=modeled_tip(model,solved)
        max_lateral=max(max_lateral,math.hypot(tip[0]-origin[0],tip[1]-origin[1]))
        max_vertical=max(max_vertical,abs(tip[2]-(origin[2]+vertical_delta*sample.cosine_eased_fraction)))
    if max_lateral>.05 or max_vertical>.02:
        raise ValueError('Direct press reference deviates from virtual vertical path')
    return dict(status='PREVIEW_ONLY_NOT_EXECUTABLE',starting_pose=start,
        target_pose=list(target),target_joints_rad=[*inverse(*target),*joints[4:]],
        experiment='POST_TRANSFER_TIP_PRESS_2MM_V1' if post_transfer else 'LOCAL_HYPOTHETICAL_TIP_RETRACT_2MM_V1' if retract else 'LOCAL_HYPOTHETICAL_TIP_PRESS_2MM_V1',
        source_export='wizard-20260917T200832068764Z-2195fd95cacf4df8ac543603873af2aa' if post_transfer else RETRACT_SOURCE if retract else SOURCE,
        sample_count=len(trace.samples),desired_tip_mm=[origin[0],origin[1],origin[2]+vertical_delta],
        maximum_lateral_drift_mm=max_lateral,maximum_vertical_error_mm=max_vertical,
        motion_authorized=False,tool_clearance_verified=False,compensation_applied=False)
