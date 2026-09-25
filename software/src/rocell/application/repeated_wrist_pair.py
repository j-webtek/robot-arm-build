"""Explicit one-count start intervals for a fixed, direction-specific wrist pair."""
import hashlib
import math
from .ascending_wrist_candidate import frozen_candidate as ascending
from .descending_wrist_transfer import frozen_candidate as descending
from .asynchronous_response_review import review_response_envelope
from .first_motion_contract import canonical


def pair_candidate(model,start,direction):
    if direction not in ('up','down'):raise ValueError('Named pair direction required')
    parent=ascending() if direction=='up' else descending()
    anchor=parent['baseline_joints_rad']
    if len(start)!=6 or any(type(x) not in (int,float) or not math.isfinite(x) for x in start):
        raise ValueError('Six finite joints required')
    width=2*math.pi/4096+1e-8  # Accommodate nine-decimal feedback serialization.
    if any(abs(a-b)>(width if i==3 else 1e-8) for i,(a,b) in enumerate(zip(start,anchor))):
        raise ValueError('Outside explicitly reviewed fixed-pair start interval')
    wire=list(parent['transmitted_joints_rad']);desired=list(parent['desired_joints_rad'])
    # No coefficient/target fitting: only the baseline and swept geometry change.
    for wrist in (anchor[3]-width,anchor[3]+width):
        extreme=list(anchor);extreme[3]=wrist
        review=review_response_envelope(model,extreme,wire,extra_steps=1)
        if review['status']!='NO_SAMPLED_EXCEEDANCE':raise ValueError('Start interval envelope rejected')
    preview=review_response_envelope(model,start,wire,extra_steps=1)
    result=dict(parent,baseline_joints_rad=list(start),preview=preview,
        parent_source_sha256=parent['source_sha256'],pair_direction=direction,
        start_interval_center_rad=anchor[3],start_interval_half_width_rad=width,
        correction_refitted=False)
    result.pop('candidate_sha256',None)
    return dict(result,candidate_sha256=hashlib.sha256(canonical(result)).hexdigest())


def run_two_pairs(*,run_leg,verify_leg,cancelled=lambda:False):
    """Four legs maximum; failed publication or observation never triggers return."""
    legs=[]
    for direction in ('up','down','up','down'):
        if cancelled():return dict(status='CANCELLED',legs=legs)
        try:result=run_leg(direction)
        except Exception:return dict(status='LEG_OUTCOME_UNCERTAIN',legs=legs)
        legs.append(result)
        if result.get('status')!='VERIFIED_AND_EXPORTED':
            return dict(status='STOPPED_ON_LEG_FAILURE',legs=legs)
        try:
            if verify_leg(result,direction) is not True:
                return dict(status='STOPPED_ON_EXPORT_REVIEW',legs=legs)
        except Exception:
            return dict(status='STOPPED_ON_EXPORT_REVIEW',legs=legs)
    return dict(status='TWO_REPORTED_PAIRS_VERIFIED',legs=legs,physical_accuracy_verified=False)
