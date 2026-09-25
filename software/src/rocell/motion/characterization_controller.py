"""Bounded campaign diagnostics using the existing audited T104 math model.

These samples have interpolation indices, not elapsed times. They must never be
fed into settling analysis with invented servo timing. Reference IK screening
does not establish installed joint limits, clearance or command admission.
"""

import math

from rocell.kinematics.firmware_reference import forward, inverse, REFERENCE_SHA256
from rocell.simulation.controller import ControllerPose, simulate_t104_trace, ControllerSimulationError
from .characterization_plan import FrozenCampaign


def _screen_reference_trace(trace):
    """Check every bounded interpolation sample, retaining the first failure.

    Only the regular positive-radius branch is implemented by the reference.
    A rejected branch is unsupported here, not proof the real arm cannot reach
    it. Roll/gripper are outside this four-joint inverse model.
    """
    result = {'status': 'REFERENCE_IK_PASS', 'reference_sha256': REFERENCE_SHA256,
              'evaluated_samples': 0, 'first_failure': None,
              'max_roundtrip_error_mm': 0.0, 'max_adjacent_joint_delta_rad': 0.0,
              'joint_landmarks': [], 'clearance_verified': False,
              'installed_joint_limits_verified': False, 'motion_authorized': False,
              'roll_gripper_qualified': False}
    previous = None
    selected = {0, len(trace.samples)//2, len(trace.samples)-1}
    for index, sample in enumerate(trace.samples):
        pose = sample.pose
        result['evaluated_samples'] += 1
        try:
            joints = inverse(pose.x_mm, pose.y_mm, pose.z_mm, pose.pitch_rad)
            actual = forward(*joints)
            error = math.dist(actual[:3], (pose.x_mm, pose.y_mm, pose.z_mm))
            if not all(math.isfinite(v) for v in (*joints, *actual, error)):
                raise ValueError('Nonfinite reference solution')
            result['max_roundtrip_error_mm'] = max(result['max_roundtrip_error_mm'], error)
            if error > 1e-6 or abs(actual[3]-pose.pitch_rad) > 1e-8:
                raise ValueError('Reference roundtrip mismatch')
            if previous is not None:
                # Do not wrap angles: a branch jump must remain visible.
                result['max_adjacent_joint_delta_rad'] = max(
                    result['max_adjacent_joint_delta_rad'],
                    max(abs(a-b) for a,b in zip(joints, previous)))
            if index in selected:
                result['joint_landmarks'].append({'sample_index': index,
                    'joints_rad': dict(zip(('base','shoulder','elbow','wrist_pitch'), joints))})
            previous = joints
        except (ValueError, OverflowError, ZeroDivisionError):
            result['status'] = 'REFERENCE_IK_UNRESOLVED'
            result['first_failure'] = {'sample_index': index, 'pose': pose.to_dict(),
                                      'reason': 'REGULAR_BRANCH_OR_ROUNDTRIP_FAILED'}
            break
    return result


def controller_campaign_preview(plan: FrozenCampaign) -> dict:
    if type(plan) is not FrozenCampaign:
        raise ValueError('Expected frozen campaign')
    data=plan.to_dict()
    report={'schema':'rocell.characterization_controller.v1','plan_sha256':plan.sha256,
            'model':'EXISTING_CONTROLLER_T104_COSINE_INTERPOLATION',
            'timing_available':False,'installed_firmware_verified':False,
            'reference_observation':'MAIN_LOOP_FEEDBACK_BLOCKED_DURING_T104',
            'stop_semantics':'INTERPOLATION_EXIT_NOT_VERIFIED_SERVO_HOLD',
            'motion_authorized':False,'physical_ready':False,'trials':[]}
    if data['frame']!='R_ctrl':
        report['status']='CONTROLLER_FRAME_REQUIRED'
        return report
    remaining=4096
    for trial in data['trials']:
        poses=[ControllerPose(p['x_mm'],p['y_mm'],p['z_mm'],p['pitch_rad'],p['roll_rad'],p['gripper_rad'])
               for p in (trial['start'],trial['target'])]
        row={'trial_id':trial['trial_id'],'spd_coefficient':trial['spd'],
             'duration_s':None,'ik':'NOT_SOLVED','physical_ready':False}
        if remaining<2:
            row.update(status='TRACE_BUDGET_EXCEEDED',sample_count=None)
        else:
            try:
                trace=simulate_t104_trace(*poses,spd_coefficient=trial['spd'],maximum_samples=min(512,remaining))
                remaining-=len(trace.samples)
                row['reference_ik'] = _screen_reference_trace(trace)
                row['ik'] = row['reference_ik']['status']
                # Keep compact landmarks; the entire trace is deterministic
                # from the hashed plan and model source, not saved servo data.
                selected=sorted({0,len(trace.samples)//2,len(trace.samples)-1})
                row.update(status='MODELED_UNTIMED_TRACE',sample_count=len(trace.samples),
                           delta_mixed_units=trace.delta_mixed_units,
                           zero_cartesian_delta=trace.zero_motion_delta,
                           landmarks=[trace.samples[i].to_dict() for i in selected],
                           gripper_target_applied_without_cartesian_easing=poses[0].gripper_raw_rad!=poses[1].gripper_raw_rad)
            except (ControllerSimulationError,OverflowError):
                row.update(status='TRACE_UNAVAILABLE_WITHIN_MODEL_BOUNDS',sample_count=None)
        report['trials'].append(row)
    report['status']='MODELED_UNTIMED_TRACES' if all(r['status']=='MODELED_UNTIMED_TRACE' for r in report['trials']) else 'INCOMPLETE_MODEL_TRACES'
    report['reference_ik_status'] = ('REFERENCE_IK_PASS' if all(
        r['ik']=='REFERENCE_IK_PASS' for r in report['trials']) else 'REFERENCE_IK_INCOMPLETE')
    report['limitations']=[
        'Mixed mm/rad delta is retained as firmware math, not physical velocity.',
        'Speed changes interpolation increments; no command duration or servo response time is inferred.',
        'Gripper behavior is distinct from Cartesian easing and requires separate qualification.',
        'Reported endpoint math agreement does not verify physical pose or installed firmware identity.']
    report['limitations'].append('Reference IK covers one branch and four joints; joint limits, roll/gripper, collision and tool geometry remain unqualified.')
    report['limitations'].append('Pinned reference T104 blocks normal feedback refresh; continuous in-motion monitoring is not established.')
    return report
