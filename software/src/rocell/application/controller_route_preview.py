"""Finite two-leg R_ctrl preview from saved telemetry; never a motion permit."""
import math
from rocell.kinematics.firmware_reference import forward, inverse, REFERENCE_SHA256


def _baseline(report):
    if (report.get('status') != 'SUCCEEDED' or report.get('identity_before_matched') is not True
            or report.get('identity_after_matched') is not True):
        raise ValueError('Identity-matched successful feedback required')
    joints = report.get('joints_rad') or {}
    values = (report.get('controller_cartesian') or {}).get('values') or {}
    start = [values.get(key) for key in ('x','y','z','tit')]
    raw_joints = [joints.get(key) for key in ('b','s','e','t','r','g')]
    if any(type(v) not in (int,float) or not math.isfinite(v) for v in start+raw_joints):
        raise ValueError('Complete finite Cartesian and joint feedback required')
    predicted = forward(*raw_joints[:4])
    consistent = math.dist(start[:3],predicted[:3]) <= .01 and abs(start[3]-predicted[3]) <= 1e-5
    return start,raw_joints,consistent


def preview_vertical_pair(report, *, step_mm=2):
    """Screen fixed +2/+5 mm geometry, not timing, clearance or authority."""
    if type(step_mm) is not int or step_mm not in (2,5):
        raise ValueError('Only named 2 mm and 5 mm diagnostic steps are supported')
    start,raw_joints,consistent=_baseline(report)
    result = dict(schema='rocell.controller_vertical_preview.v1', frame='R_ctrl',
        reference_sha256=REFERENCE_SHA256, starting_pose=start, reported_joints_rad=dict(report['joints_rad']),
        baseline_reference_consistent=consistent, source_response_sha256=report.get('response_sha256'),
        historical_feedback_only=True, command_count=0, motion_authorized=False,step_mm=step_mm,
        full_arm_clearance_verified=False, board_registration_applied=False,
        installed_tool_verified=False, timing_simulated=False, legs=[])
    if not consistent:
        return dict(result,status='REFERENCE_MISMATCH')
    bounds = ((-math.pi,math.pi),(-math.pi/2,math.pi/2),(-1,2.95),(-math.pi/2,math.pi/2))
    previous = raw_joints[:4]
    for leg, z0, z1 in (('out',start[2],start[2]+step_mm),('return',start[2]+step_mm,start[2])):
        samples = []
        for index in range(41):
            target = (start[0],start[1],z0+(z1-z0)*index/40,start[3])
            try:
                solution = inverse(*target)
            except ValueError:
                result['legs'].append(dict(leg=leg,status='IK_DOMAIN_REJECTED',samples=samples))
                return dict(result,status='PREVIEW_REJECTED')
            recovered = forward(*solution)
            accepted = (all(lo <= angle <= hi for angle,(lo,hi) in zip(solution,bounds))
                and max(abs(a-b) for a,b in zip(solution,raw_joints[:4])) <= math.radians(3)
                and max(abs(a-b) for a,b in zip(solution,previous)) <= math.radians(1)
                and math.dist(target[:3],recovered[:3]) < 1e-6
                and abs(target[3]-recovered[3]) < 1e-8)
            samples.append(dict(fraction=index/40, target_xyz_pitch=list(target),
                                predicted_arm_joints_rad=list(solution), accepted=accepted))
            if not accepted:
                result['legs'].append(dict(leg=leg,status='JOINT_OR_ROUNDTRIP_REJECTED',samples=samples))
                return dict(result,status='PREVIEW_REJECTED')
            previous = solution
        result['legs'].append(dict(leg=leg,status='SAMPLED_REFERENCE_PASS',samples=samples))
    result['maximum_joint_change_deg'] = [max(abs(math.degrees(s['predicted_arm_joints_rad'][i]-raw_joints[i]))
        for leg in result['legs'] for s in leg['samples']) for i in range(4)]
    return dict(result,status='PREVIEW_ONLY_NOT_EXECUTABLE')


def preview_elbow_isolation(report, *, elbow_degrees=2):
    """Named -2/-5 degree elbow lift, all other joints left uncommanded.

    Nominal displacement limits are 15/35 mm respectively. The 5-degree option
    is an explicitly selected visibility diagnostic, not arbitrary motion.
    No physical clearance is inferred.
    """
    if type(elbow_degrees) is not int or elbow_degrees not in (2,5,-3,1,-1,3,-4,-5,-6,-7,-8,-9,-10):
        raise ValueError('Only named 2/5 degree lifts or 3 degree reverse probe supported')
    start,joints,consistent=_baseline(report)
    result=dict(schema='rocell.controller_elbow_preview.v1',starting_pose=start,
        reported_joints_rad=dict(report['joints_rad']),reference_sha256=REFERENCE_SHA256,
        command_count=0,motion_authorized=False,full_arm_clearance_verified=False,
        baseline_reference_consistent=consistent,samples=[])
    if not consistent:
        return dict(result,status='REFERENCE_MISMATCH')
    # Negative lift means a +3-degree elbow comparison, confined to the
    # observed interval of the September 17 trials (not a generic return).
    if elbow_degrees==-3 and not (1.4942677294<=joints[2] and joints[2]+math.radians(3)<=1.581534192):
        return dict(result,status='REVERSE_PROBE_OUTSIDE_REVIEWED_INTERVAL')
    target_elbow=joints[2]-math.radians(elbow_degrees)
    if elbow_degrees in (-7,-8,-9,-10):
        # Named comparison after the reverse Cartesian discrepancy, not a
        # seven-degree move. Preserve the previous reverse elbow goal exactly.
        fixed=(.001533981,.033747577,1.67357304,-.052155347,.018407769,3.138524692)
        if elbow_degrees in (-9,-10):
            fixed=(.001533981,.033747577,1.691980809,-.052155347,.018407769,3.138524692)
        if any(abs(a-b)>1e-8 for a,b in zip(joints,fixed)):
            return dict(result,status='ISOLATED_COMPARISON_START_MISMATCH')
        target_elbow=1.6579063063032675
        result['experiment']='POST_TIP_REVERSE_ELBOW_ISOLATION_V1'
        if elbow_degrees==-8:
            # Legacy numeric selector denotes this fixed experiment, NOT 8 deg.
            # Opposite-direction response test, smaller than the previous move.
            target_elbow=1.68557304
            result['experiment']='POST_TIP_ELBOW_PLUS_0P012_RAD_V1'
        if elbow_degrees in (-9,-10):
            target_elbow=1.683980809
            result['experiment']='POST_OVERSHOOT_ELBOW_MINUS_0P008_RAD_V1'
            if elbow_degrees==-10:result['experiment']='POST_OVERSHOOT_ELBOW_SPEED40_V1'
        result['servo_speed']=40 if elbow_degrees==-10 else 20
        result['servo_acceleration']=1
    if elbow_degrees in (1,-1,3,-4,-5,-6):
        from .elbow_local_candidate import candidate_record
        candidate=candidate_record(extended_start=elbow_degrees==-1,nearby_target=elbow_degrees==3,descending=elbow_degrees==-4,descending_revised=elbow_degrees==-5,mapping_sample=elbow_degrees==-6)
        if not candidate['minimum_start_rad']<=joints[2]<=candidate['maximum_start_rad']:
            return dict(result,status='CANDIDATE_START_OUTSIDE_LOCAL_RANGE')
        target_elbow=candidate['command_rad']
        result['local_candidate']=candidate
    bounds=((-math.pi,math.pi),(-math.pi/2,math.pi/2),(0,2.95),(-math.pi/2,math.pi/2))
    for i in range(41):
        sample=list(joints)
        sample[2]=joints[2]+(target_elbow-joints[2])*i/40
        pose=forward(*sample[:4])
        if (not all(lo<=v<=hi for v,(lo,hi) in zip(sample[:4],bounds))
                or math.dist(start[:3],pose[:3])>({2:15,5:35,-3:20,1:12,-1:12,3:12,-4:28,-5:28,-6:28,-7:6,-8:6,-9:6,-10:6}[elbow_degrees])):
            return dict(result,status='PREVIEW_REJECTED')
        result['samples'].append(dict(fraction=i/40,joints_rad=sample,xyz_pitch=list(pose)))
    result['target_joints_rad']=result['samples'][-1]['joints_rad']
    result['target_pose']=result['samples'][-1]['xyz_pitch']
    if elbow_degrees in (-7,-8,-9,-10):
        from pathlib import Path
        from rocell.geometry import UrdfModel
        from .wrist_tip_review import modeled_tip
        model=UrdfModel.from_file(Path(__file__).resolve().parents[3]/'models/roarm_m3/roarm_m3_kinematic_40dbd84.urdf')
        origin=modeled_tip(model,joints)
        result['hypothetical_tip_sweep_mm']=max(math.dist(origin,modeled_tip(model,s['joints_rad'])) for s in result['samples'])
        if result['hypothetical_tip_sweep_mm']>6:return dict(result,status='PREVIEW_REJECTED')
    return dict(result,status='PREVIEW_ONLY_NOT_EXECUTABLE')
