"""Offline transfer of an existing descending correction; never refit on return."""
import hashlib
import math
from .first_motion_contract import canonical
from .asynchronous_response_review import review_response_envelope
from .wrist_tip_review import modeled_tip

PARENT_HASH='7aff3b4ac17b7c6d24843192a57426fab456508c74d2328e442a989e3134c834'


def frozen_candidate():
    """Load the immutable transfer; no runtime fitting or target substitution."""
    from pathlib import Path
    from .product_ghost_export_review import _read
    report,digest=_read(Path(__file__).resolve().parents[3]/'runs/wizard-exports',
        'wizard-20260917T210608124033Z-f9f0476934ab49249726610c4cd642ad',
        'attachment-descending-wrist-transfer.json')
    c=report['candidate'];unsigned={k:v for k,v in c.items() if k!='candidate_sha256'}
    expected='956ef6b3571719a1ab2ff1c7fea37ff51f84f1ed5f02f749cdf2f48cc8953373'
    if c.get('candidate_sha256')!=expected or hashlib.sha256(canonical(unsigned)).hexdigest()!=expected:
        raise ValueError('Frozen descending transfer changed')
    return dict(c,source_sha256=digest)


def build_descending_transfer(model,parent,ascending_trial):
    unsigned={k:v for k,v in parent.items() if k!='candidate_sha256'}
    if parent.get('candidate_sha256')!=PARENT_HASH or hashlib.sha256(canonical(unsigned)).hexdigest()!=PARENT_HASH:
        raise ValueError('Unchanged frozen descending parent required')
    tx=ascending_trial['transaction']
    if (tx['state']!='REPORTED_SETTLED_PENDING_EXPORT' or not tx['compensation_applied']
            or len(tx['rows'])<3 or ascending_trial.get('acknowledgment_received') is not True):
        raise ValueError('Exported ascending desired-endpoint completion required')
    start=list(tx['rows'][-1]['reported_joints_rad'])
    # Recheck the retained tail instead of accepting a success label alone.
    tail=[r for r in tx['rows'] if r['observed_s']>=tx['rows'][-1]['observed_s']-2.5]
    if len(tail)<3 or tail[-1]['observed_s']-tail[0]['observed_s']<2:
        raise ValueError('Two-second retained stable tail required')
    previous=None
    for row in tail:
        q=row['reported_joints_rad'];now=row['observed_s']
        if previous is not None and not 0<now-previous<=1:
            raise ValueError('Ordered bounded tail required')
        if (math.dist(modeled_tip(model,q),modeled_tip(model,tx['desired_joints_rad']))>.5
                or max(abs(a-b) for a,b in zip(q,tx['desired_joints_rad']))>.004
                or max(abs(a-b) for a,b in zip(q,start))>2*math.pi/4096):
            raise ValueError('Verified stable desired endpoint required')
        previous=now
    desired=list(start);desired[3]=tx['baseline']['joints_rad']['t']
    wire=list(desired);wire[3]-=parent['training_residual_rad']
    if not wire[3]<desired[3]<start[3] or start[3]-wire[3]>math.radians(1.5):
        raise ValueError('Bounded descending transfer required')
    # These arrays are only historical proposed starts; live use must obtain and
    # match fresh feedback. Do not reuse ascending normalization on the return.
    for q in (start,desired,wire):modeled_tip(model,q)
    envelope=review_response_envelope(model,start,wire,extra_steps=1)
    if envelope['status']!='NO_SAMPLED_EXCEEDANCE':raise ValueError('Descending envelope rejected')
    candidate=dict(schema='rocell.descending_wrist_transfer.v1',
        parent_candidate_sha256=PARENT_HASH,
        training_residual_rad=parent['training_residual_rad'],
        baseline_joints_rad=start,desired_joints_rad=desired,transmitted_joints_rad=wire,
        command=dict(T=101,joint=4,rad=wire[3],spd=20,acc=1),preview=envelope,
        maximum_command_delta_rad=math.radians(1.5),
        prospective_validation_required=True,motion_authorized=False,physical_accuracy_verified=False,
        correction_refitted=False)
    return dict(candidate,candidate_sha256=hashlib.sha256(canonical(candidate)).hexdigest())
