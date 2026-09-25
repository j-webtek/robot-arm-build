"""Fixed -1.5 degree wrist-pitch identification at the post-approach posture."""
import math
import hashlib
from .first_motion_contract import canonical
from .controller_route_preview import _baseline
from rocell.kinematics.firmware_reference import forward


def preview_post_tip_wrist(feedback, *, reverse=False, post_overshoot=False):
    """Uncompensated response discriminator; not a retry or fitted correction."""
    from pathlib import Path
    from rocell.geometry import UrdfModel
    from .wrist_tip_review import modeled_tip
    if type(reverse) is not bool or type(post_overshoot) is not bool or (reverse and post_overshoot):
        raise ValueError('Explicit diagnostic direction required')
    start, joints, consistent = _baseline(feedback)
    fixed = (.001533981, .033747577, 1.67357304, -.052155347, .018407769, 3.138524692)
    if post_overshoot:
        # Separate identification trial, not transfer of the earlier correction.
        fixed = (.001533981, .033747577, 1.691980809, -.052155347, .018407769, 3.138524692)
    if reverse:
        fixed = (.001533981, .033747577, 1.67357304, -.072097097, .018407769, 3.138524692)
    if not consistent or any(abs(a-b)>1e-8 for a,b in zip(joints,fixed)):
        raise ValueError('Exact post-tip diagnostic posture required')
    model = UrdfModel.from_file(Path(__file__).resolve().parents[3] /
                               'models/roarm_m3/roarm_m3_kinematic_40dbd84.urdf')
    origin = modeled_tip(model, joints)
    samples = []
    maximum_tip_sweep = 0.
    goal = joints[3] + math.radians(1.5 if reverse else -1.5)
    for i in range(41):
        target = list(joints)
        target[3] = joints[3] + (goal-joints[3])*i/40
        if i == 40:
            target[3] = goal
        pose = forward(*target[:4])
        maximum_tip_sweep = max(maximum_tip_sweep, math.dist(origin, modeled_tip(model,target)))
        if math.dist(start[:3],pose[:3])>6 or maximum_tip_sweep>6:
            raise ValueError('Diagnostic arc exceeds 6 mm')
        samples.append(dict(joints_rad=target,xyz_pitch=list(pose)))
    return dict(status='PREVIEW_ONLY_NOT_EXECUTABLE', starting_pose=start,
                target_pose=samples[-1]['xyz_pitch'],target_joints_rad=samples[-1]['joints_rad'],
                samples=samples,hypothetical_tip_sweep_mm=maximum_tip_sweep,
                motion_authorized=False,compensation_applied=False,local_candidate=None)


def wrist_candidate_record(*,extended_start=False,post_coordinated=False,nearby=False,ascending=False):
    if ascending:
        if not post_coordinated or extended_start or nearby:raise ValueError('Exclusive ascending candidate required')
        residual=-.072097097-(-.06739288922008504)
        record=dict(schema='rocell.post_coordinated_wrist_ascending.v1',desired_joint_index=3,
            training_export='wizard-20260917T180217981403Z-efa28b4ae1f64b19b7a1382dbcc48c75',
            desired_rad=-.055,command_rad=-.055-residual,training_residual_rad=residual,
            direction='INCREASING_WRIST_PITCH',spd=20,acc=1,globally_enabled=False,
            minimum_start_rad=-.072097097-1e-8,maximum_start_rad=-.072097097+1e-8)
        return dict(record,candidate_sha256=hashlib.sha256(canonical(record)).hexdigest())
    if nearby and not post_coordinated:raise ValueError('Nearby target requires post-coordinated scope')
    if post_coordinated and extended_start:raise ValueError('Exclusive candidate scope required')
    if post_coordinated:
        residual=-.075165059-(-.09214111277991494)
        record=dict(schema='rocell.post_coordinated_wrist_candidate.v1',desired_joint_index=3,
            training_export='wizard-20260917T175637612429Z-34ef0ef0e9484ef7810967bb31445882',
            desired_rad=-.085,command_rad=-.085-residual,training_residual_rad=residual,
            direction='DECREASING_WRIST_PITCH',spd=20,acc=1,globally_enabled=False,
            minimum_start_rad=-.075165059-1e-8,maximum_start_rad=-.075165059+1e-8)
        if nearby:
            # Translate the target by the previous reported step without refitting bias.
            record.update(schema='rocell.post_coordinated_wrist_candidate.v2',
                parent_candidate_sha256=wrist_candidate_record(post_coordinated=True)['candidate_sha256'],
                desired_rad=-.094203884,command_rad=-.094203884-residual,
                minimum_start_rad=-.084368943-1e-8,maximum_start_rad=-.084368943+1e-8)
        return dict(record,candidate_sha256=hashlib.sha256(canonical(record)).hexdigest())
    residual=.026077673-.012169581220085053
    record=dict(schema='rocell.post_approach_wrist_candidate.v1',desired_joint_index=3,
        training_export='wizard-20260917T171702860871Z-6310136178104360ac605fb7c4263618',
        desired_rad=.010,command_rad=.010-residual,training_residual_rad=residual,
        direction='DECREASING_WRIST_PITCH',spd=20,acc=1,globally_enabled=False)
    if extended_start:
        record.update(schema='rocell.post_approach_wrist_candidate.v2',
                      minimum_start_rad=.018,maximum_start_rad=.027,
                      parent_candidate_sha256=wrist_candidate_record()['candidate_sha256'])
    return dict(record,candidate_sha256=hashlib.sha256(canonical(record)).hexdigest())


def preview_wrist_probe(feedback,*,candidate=False,prepare=False,post_coordinated=False,ascending=False):
    if candidate in ('pair-down','pair-up'):
        if not post_coordinated or prepare or ascending!=(candidate=='pair-up'):
            raise ValueError('Exclusive directional pair leg required')
        from .wrist_shared_pair import preview_pair_leg
        return preview_pair_leg(feedback,candidate.removeprefix('pair-'))
    if type(ascending) is not bool or (ascending and (not post_coordinated or candidate in ('extended-start','nearby-target') or prepare)):
        raise ValueError('Exclusive ascending diagnostic required')
    if type(post_coordinated) is not bool or (post_coordinated and (candidate=='extended-start' or prepare)):
        raise ValueError('Exclusive post-coordinated diagnostic required')
    if type(candidate) is not bool and candidate not in ('extended-start','nearby-target'):raise ValueError('Named wrist candidate required')
    if candidate=='nearby-target' and not post_coordinated:raise ValueError('Nearby candidate requires post-coordinated scope')
    if candidate and prepare: raise ValueError('Exclusive wrist experiment required')
    start,joints,consistent=_baseline(feedback)
    fixed=(.001533981,.007669904,1.563126423,None,.01994175,3.138524692)
    lo,hi=(.025,.027) if candidate else (.030,.045)
    if candidate=='extended-start':lo,hi=.018,.027
    if prepare:lo,hi=.005,.012
    if post_coordinated:
        fixed=(.001533981,.033747577,1.636757501,None,.018407769,3.138524692)
        lo,hi=-.065961174-1e-8,-.065961174+1e-8
        if candidate:lo,hi=-.075165059-1e-8,-.075165059+1e-8
        if candidate=='nearby-target':lo,hi=-.084368943-1e-8,-.084368943+1e-8
        if ascending:lo,hi=-.093572828-1e-8,-.093572828+1e-8
        if ascending and candidate:lo,hi=-.072097097-1e-8,-.072097097+1e-8
    if (not consistent or not lo<=joints[3]<=hi
            or any(abs(value-fixed[i])>1e-8 for i,value in enumerate(joints) if i!=3)):
        raise ValueError('Post-approach posture required')
    samples=[]
    record=wrist_candidate_record(extended_start=candidate=='extended-start',post_coordinated=post_coordinated,nearby=candidate=='nearby-target',ascending=ascending) if candidate else None
    goal=record['command_rad'] if record else joints[3]-math.radians(1.5)
    if ascending and not candidate:goal=joints[3]+math.radians(1.5)
    if prepare:goal=.026077673
    for i in range(41):
        target=list(joints); target[3]+=(goal-joints[3])*i/40
        if i==40:target[3]=goal  # Preserve the exact frozen command at the endpoint.
        pose=forward(*target[:4])
        if math.dist(start[:3],pose[:3])>6: raise ValueError('Wrist sweep exceeds 6 mm')
        samples.append(dict(joints_rad=target,xyz_pitch=list(pose)))
    return dict(status='PREVIEW_ONLY_NOT_EXECUTABLE',starting_pose=start,
                target_pose=samples[-1]['xyz_pitch'],target_joints_rad=samples[-1]['joints_rad'],
                samples=samples,motion_authorized=False,compensation_applied=bool(candidate),local_candidate=record)
