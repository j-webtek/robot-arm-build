"""Frozen one-point ascending-elbow candidate, not global compensation."""
import hashlib
import math
from .first_motion_contract import canonical
from rocell.kinematics.firmware_reference import forward

CANDIDATE=dict(schema='rocell.elbow_local_candidate.v1',
    training_export='wizard-20260917T162113108962Z-9d5d681c4a304b0195449e2e0ab3f489',
    desired_rad=1.5633309535598299,command_rad=1.5543315991196598,
    training_residual_rad=0.008999354440170082,spd=20,acc=1,
    approach='INCREASING_ELBOW_RAD',minimum_start_rad=1.525,maximum_start_rad=1.54,
    globally_enabled=False,held_out_validation=True)


def candidate_record(*, extended_start=False, nearby_target=False, descending=False, descending_revised=False, mapping_sample=False):
    """Keep the original identity intact; extension is a separate experiment."""
    record=dict(CANDIDATE)
    if sum(bool(v) for v in (extended_start,nearby_target,descending,descending_revised,mapping_sample))>1:
        raise ValueError('Select one named experiment')
    if extended_start:
        record.update(schema='rocell.elbow_local_candidate.v2',minimum_start_rad=1.520,
                      parent_candidate_sha256=candidate_record()['candidate_sha256'])
    if nearby_target:
        # Predeclared held-out target, not a fit to the upcoming observation.
        record.update(schema='rocell.elbow_local_candidate.v3',minimum_start_rad=1.520,
                      desired_rad=CANDIDATE['desired_rad']-.01,
                      command_rad=CANDIDATE['command_rad']-.01,
                      parent_candidate_sha256=candidate_record(extended_start=True)['candidate_sha256'])
    if descending or descending_revised or mapping_sample:
        # Residual repeated in two preparation trials; never reuse ascending fit.
        residual=1.523242922-1.4758599604002836
        record.update(schema='rocell.elbow_local_descending.v1',
                      training_export='wizard-20260917T163506671259Z-de320d9a030045a3a03e24bfa4bff6a7',
                      corroborating_export='wizard-20260917T164028812312Z-ede1be83a00144d48545ebaea698d838',
                      desired_rad=1.530,command_rad=1.530-residual,
                      training_residual_rad=residual,approach='DECREASING_ELBOW_RAD',
                      minimum_start_rad=1.550,maximum_start_rad=1.565)
        if descending_revised:
            # Equal weight to distinct operating points, not duplicate trials.
            revised=(residual+0.04982976859971644)/2
            record.update(schema='rocell.elbow_local_descending.v2',
                          command_rad=1.530-revised,training_residual_rad=revised,
                          additional_training_export='wizard-20260917T164349530197Z-3680dd0bc2134fbbbdc37b07ec807f84',
                          parent_candidate_sha256=candidate_record(descending=True)['candidate_sha256'])
        if mapping_sample:
            record.update(schema='rocell.elbow_response_sample.v1',
                          command_rad=1.4758599604002836,training_residual_rad=None,
                          minimum_start_rad=1.552388557-1e-8,
                          maximum_start_rad=1.552388557+1e-8,
                          purpose='FIXED_START_IDENTIFICATION_NOT_FITTED_CORRECTION')
    return dict(record,candidate_sha256=hashlib.sha256(canonical(record)).hexdigest())


def evaluate_desired_endpoint(baseline_joints,rows,*,candidate=None):
    """Keep the intended endpoint separate from strict wire-goal verification."""
    if not rows: return dict(status='NO_OBSERVATIONS',physical_accuracy_verified=False)
    selected=candidate or CANDIDATE
    joint_index=selected.get('desired_joint_index',2)
    if selected.get('schema') in ('rocell.coordinated_offset_candidate.v1','rocell.post_tip_wrist_candidate.v1'):
        desired=selected['desired_joints_rad']
        if len(desired)!=6 or any(type(v) not in (int,float) or not math.isfinite(v) for v in desired):
            raise ValueError('Complete finite desired joints required')
        joint_index=None
    else:
        if joint_index not in (2,3): raise ValueError('Unsupported desired joint')
        desired=list(baseline_joints); desired[joint_index]=selected['desired_rad']
    target=forward(*desired[:4]); last=rows[-1]
    error=math.dist(target[:3],last[2][:3])
    # Reuse the transaction's numeric tolerance and dwell, without relabeling
    # its wire-target outcome. This is reported-state evidence only.
    since=None; count=0; verified=False
    for begin,end,pose,joints in rows:
        good=(math.dist(target[:3],pose[:3])<=.5 and abs(target[3]-pose[3])<=.02
              and max(abs(a-b) for a,b in zip(desired,joints))<=.02)
        if good:
            if since is None: since=end
            count+=1
        else: since=None; count=0
        verified=good and count>=3 and begin-since>=500_000_000
    return dict(status='DESIRED_REPORTED_ENDPOINT_VERIFIED' if verified else 'DESIRED_ENDPOINT_NOT_VERIFIED',
        desired_xyz_pitch=list(target),position_error_mm=error,
        **({'joint_errors_deg':[math.degrees(a-b) for a,b in zip(last[3],desired)]} if joint_index is None else
           {('elbow_error_deg' if joint_index==2 else 'wrist_error_deg'):math.degrees(last[3][joint_index]-desired[joint_index])}),
        physical_accuracy_verified=False,wire_target_verdict_unchanged=True)
