"""One reference-count normalization candidate, not a fitted or deployed model."""
import math
from .asynchronous_response_review import review_response_envelope
from .wrist_tip_review import modeled_tip

COUNT_RAD=2*math.pi/4096


def frozen_candidate():
    """Read the reviewed immutable candidate; reject altered export contents."""
    from pathlib import Path
    from .product_ghost_export_review import _read
    report,digest=_read(Path(__file__).resolve().parents[3]/'runs/wizard-exports',
        'wizard-20260917T210045168003Z-73665e7b0aba485fb85dc2953869ad48',
        'attachment-ascending-count-candidate.json')
    if digest!='4330a2944a252e301ea90b6a66556e741f37665ad1c46fc615331bbcadbfa53d':
        raise ValueError('Frozen candidate hash mismatch')
    return dict(report['candidate'],source_sha256=digest)


def evaluate_count_normalization(model, trials):
    """Evaluate a source-derived +one-count correction without fitting any trial.

    Reference command midpoint 2047 vs feedback midpoint 2048 motivates the
    correction. Adding it to an observed response is a counterfactual constant-
    response assumption, not an actually observed compensated endpoint.
    """
    if len(trials)<2:raise ValueError('Independent ascending records required')
    rows=[]
    for trial in trials:
        c=trial['command'];w=trial['wrist']
        if (c['T']!=101 or c['joint']!=4 or c['spd']!=20 or c['acc']!=1
                or w['ideal_delta_deg']<=0 or w['reported_delta_deg']<=0
                or trial['maximum_other_joint_change_rad']>1e-8):
            raise ValueError('Interpretable ascending wrist-only response required')
        desired=list(trial['baseline_joints_rad']);desired[3]=c['rad']
        shifted=list(trial['final_joints_rad']);shifted[3]+=COUNT_RAD
        rows.append(dict(observed_wire_residual_rad=w['ideal_error_rad'],
            counterfactual_corrected_residual_rad=w['ideal_error_rad']+COUNT_RAD,
            counterfactual_tip_error_mm=math.dist(modeled_tip(model,desired),modeled_tip(model,shifted))))
    return dict(schema='rocell.ascending_count_normalization.v1',
        correction_rad=COUNT_RAD,correction_basis='REFERENCE_MIDPOINT_DIFFERENCE_NOT_FITTED',
        comparisons=rows,prospectively_validated=False,motion_authorized=False,
        physical_accuracy_verified=False)


def preview_candidate(model, start):
    desired=list(start);wire=list(start)
    # Separate new endpoint, chosen before any compensated trial.
    desired[3]=-.045;wire[3]=desired[3]+COUNT_RAD
    if not 0<wire[3]-start[3]<=.016:
        raise ValueError('Small ascending candidate only')
    stress=review_response_envelope(model,start,wire,extra_steps=1)
    if stress['status']!='NO_SAMPLED_EXCEEDANCE':raise ValueError('Envelope rejected')
    return dict(baseline_joints_rad=list(start),desired_joints_rad=desired,
        transmitted_joints_rad=wire,command=dict(T=101,joint=4,rad=wire[3],spd=20,acc=1),
        correction_rad=COUNT_RAD,preview=stress,motion_authorized=False,
        status='OFFLINE_CANDIDATE_NOT_ADMITTED',physical_accuracy_verified=False)
