"""Offline matched-history A/B design. No command transport or motion authority."""
from .characterization_admission import encode_manifest
from .local_pair_offset import pair


def draft_comparison(proposal, bounds):
    """Two separate three-leg campaigns, each with the same conditioning path.

    A small final control response is an experimental result, not permission to
    continue through a controller fault. No recovery/return leg follows a trial.
    """
    if proposal.get('schema')!='rocell.stateful_pair_compensation.v1':
        raise ValueError('Compensation proposal required')
    anchor=pair(proposal['current_goals']); positions=pair(proposal['current_positions'])
    desired=pair(proposal['desired'])
    conditioning=pair((anchor[0]-12,anchor[1]+12))
    campaigns=[]
    for label,field in (('control','uncompensated_coupled_goals'),('compensated','proposed_goals')):
        target=pair(proposal[field])
        if target==anchor or target[0]>=anchor[0]:
            raise ValueError('Comparable outbound direction required')
        goals=[list(conditioning),list(anchor),list(target)]
        manifest=dict(goals=goals,bounds=bounds,maximum_us=60000000)
        encode_manifest(manifest,campaign='00'*32,reference='00'*32)
        if any(abs(g-p)>32 for goal in goals for g,p in zip(goal,positions)):
            raise ValueError('Conditioning exceeds measured-anchor envelope')
        low,high=pair(proposal['tested_primary_range'])
        if any(not low<=goal[0]<=high for goal in goals):
            raise ValueError('Conditioning outside empirical command interval')
        campaigns.append(dict(label=label,manifest=manifest,
            leg_roles=['conditioning_outbound','conditioning_return','trial'],
            trial_desired=list(desired),automatic_return=False))
    if campaigns[0]['manifest']['goals'][-1]==campaigns[1]['manifest']['goals'][-1]:
        raise ValueError('Distinct comparison targets required')
    return dict(schema='rocell.compensation_ab_plan.v1',campaigns=campaigns,
        frozen_model_sha256=proposal['frozen_model_sha256'],
        trial_start_reference=list(positions),matched_start_tolerance_counts=1,
        maximum_total_writes=6,order=['control','compensated'],
        independent_campaign_admission_required=True,hardware_access=False,
        movement_authorized=False,current_r38_supports_plan=False,
        comparison_is_pilot_not_repeated_validation=True)


def compare_endpoints(*, control_before, compensated_before, control_end,
                      compensated_end, desired):
    """Descriptive scoring only, after separate raw-evidence review.

    Near-matching encoder starts do not prove matching load/history. Caller must
    additionally review the identical conditioning path, goals, fresh settled
    feedback and immutable exports. No binary 'validated' decision is returned.
    """
    a,b,x,y,d=map(pair,(control_before,compensated_before,control_end,compensated_end,desired))
    mismatch=[abs(p-q) for p,q in zip(a,b)]
    errors={name:[p-q for p,q in zip(end,d)] for name,end in (('control',x),('compensated',y))}
    return dict(start_difference_counts=mismatch,starts_match_within_one_count=max(mismatch)<=1,
        signed_errors=errors,maximum_absolute_errors={k:max(map(abs,v)) for k,v in errors.items()},
        raw_evidence_review_required=True,physical_accuracy_verified=False,
        compensation_validated=False,movement_authorized=False)
