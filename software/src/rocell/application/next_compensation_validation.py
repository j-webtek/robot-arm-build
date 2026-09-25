"""Fixed follow-up validation design; pure planning, no transport authority."""
from copy import deepcopy
from .characterization_admission import encode_manifest
from .local_pair_offset import pair
from .stateful_pair_compensation import propose
from .shoulder_repeatability_plan import predict


UPPER=[2389,1725]
LOWER=[2377,1737]
FORWARD=[2378,1736]


def _manifest(goals,bounds):
    document=dict(goals=deepcopy(goals),bounds=deepcopy(bounds),maximum_us=60000000)
    encode_manifest(document,campaign='00'*32,reference='00'*32)
    if any(sum(pair(goal))!=4114 for goal in goals):
        raise ValueError('Coupled shoulder targets required')
    return document


def draft(*, frozen, bounds, installed_goals, installed_positions,
          campaign_anchor=(2391,1724)):
    """Prepare one repeat and reverse A/B; never infer a live pose."""
    installed_goals=pair(installed_goals);installed_positions=pair(installed_positions)
    campaign_anchor=pair(campaign_anchor)
    if installed_goals!=(2378,1736) or any(abs(p-r)>1 for p,r in zip(installed_positions,(2387,1730))):
        raise ValueError('Verified r40 terminal state required')
    if type(bounds) not in (list,tuple) or len(bounds)!=7:
        raise ValueError('Seven reviewed bounds required')
    forward=[UPPER,LOWER,UPPER,FORWARD]
    # The lower conditioning endpoint is the measured reference from r40.
    reverse=propose(frozen,current_goals=LOWER,current_positions=(2385,1731),
        desired=(2388,1729),bounds=bounds[1:3],tested_primary_range=(2377,2389),
        campaign_anchor=campaign_anchor)
    if reverse['uncompensated_coupled_goals']!=[2386,1728] or reverse['proposed_goals']!=[2385,1729]:
        raise ValueError('Frozen reverse proposal differs')
    reverse_candidate=[UPPER,LOWER,reverse['proposed_goals']]
    reverse_control=[UPPER,LOWER,reverse['uncompensated_coupled_goals']]
    return dict(schema='rocell.next_compensation_validation.v1',
        frozen_model_sha256=frozen['sha256'],model_refitted=False,
        required_initial=dict(goals=list(installed_goals),positions=list(installed_positions),
                              tolerance_counts=1),
        forward_repeat=dict(manifest=_manifest(forward,bounds),
            roles=['normalize_upper','conditioning_lower','conditioning_return','forward_candidate'],
            desired=[2388,1729],expected_trial_start=[2391,1724]),
        reverse_candidate=dict(manifest=_manifest(reverse_candidate,bounds),
            roles=['conditioning_upper','conditioning_lower','reverse_candidate'],
            desired=[2388,1729],expected_trial_start=[2385,1731],
            frozen_prediction=reverse['predictions']['stateful_band']),
        reverse_control=dict(manifest=_manifest(reverse_control,bounds),
            roles=['conditioning_upper','conditioning_lower','reverse_control'],
            desired=[2388,1729],expected_trial_start=[2385,1731],
            frozen_prediction=predict(frozen,target=reverse['uncompensated_coupled_goals'],
                before=(2385,1731),direction=1)['stateful_band']),
        execution_order=['forward_repeat','reverse_candidate','reverse_control'],
        maximum_total_writes=10,separate_campaign_admission_required=True,
        matched_start_tolerance_counts=1,automatic_retry=False,automatic_return=False,
        stopped_outcome_retained=True,hardware_access=False,movement_authorized=False,
        physical_accuracy_verified=False,general_compensation_validated=False)
