"""Bounded offline inverse prediction for the shoulder pair. No hardware API."""
from .local_pair_offset import pair
from .shoulder_repeatability_plan import predict


def propose(frozen, *, current_goals, current_positions, desired, bounds,
            tested_primary_range, campaign_anchor):
    """Enumerate at most 48 coupled commands; minimize predicted endpoint error.

    Search stays inside the observed command interval, but an unseen command
    within that interval is still unvalidated interpolation. Desired encoder
    positions need not sum to 4114; transmitted target registers must do so.
    The uncorrected comparator projects desired positions onto that same coupling.
    """
    current_goals,current_positions,desired,campaign_anchor=map(pair,
        (current_goals,current_positions,desired,campaign_anchor))
    if sum(current_goals)!=4114:
        raise ValueError('Reviewed target coupling required')
    if (type(bounds) not in (list,tuple) or len(bounds)!=2 or
            any(len(b)!=2 or any(type(v) is not int or not 0<=v<=4095 for v in b) or b[0]>b[1] for b in bounds)):
        raise ValueError('Two reviewed joint bounds required')
    low,high=pair(tested_primary_range)
    if low>high or not low<=current_goals[0]<=high:
        raise ValueError('Current target outside empirical range')
    for values in (current_goals,current_positions,desired,campaign_anchor):
        if any(not lo<=v<=hi for v,(lo,hi) in zip(values,bounds)):
            raise ValueError('Input outside reviewed joint bounds')
    if any(abs(p-a)>32 for p,a in zip(current_positions,campaign_anchor)):
        raise ValueError('Current pose outside campaign envelope')
    delta=[d-p for d,p in zip(desired,current_positions)]
    if not all(2<=abs(d)<=24 for d in delta) or delta[0]*delta[1]>=0:
        raise ValueError('Clear bounded opposite-direction endpoint change required')
    direction=1 if delta[0]>0 else -1
    # Verify model integrity and consistency of the supplied current state.
    current_prediction=predict(frozen,target=current_goals,before=current_positions,direction=direction)['stateful_band']
    if any(abs(p-a)>2 for p,a in zip(current_prediction,current_positions)):
        raise ValueError('Starting position contradicts frozen local band')
    candidates=[]
    for primary in range(max(low,current_goals[0]-24),min(high,current_goals[0]+24)+1):
        target=(primary,4114-primary)
        step=primary-current_goals[0]
        if step*direction<=0 or not 0<=target[1]<=4095:
            continue
        if any(not lo<=g<=hi for g,(lo,hi) in zip(target,bounds)):
            continue
        if any(abs(g-p)>32 or abs(g-a)>32 for g,p,a in zip(target,current_positions,campaign_anchor)):
            continue
        models=predict(frozen,target=target,before=current_positions,direction=direction)
        endpoint=models['stateful_band']
        if any(not lo<=p<=hi or abs(p-a)>32 for p,a,(lo,hi) in zip(endpoint,campaign_anchor,bounds)):
            continue
        error=[p-d for p,d in zip(endpoint,desired)]
        candidates.append(dict(target=list(target),models=models,predicted_error=error,
            score=(max(map(abs,error)),sum(e*e for e in error),abs(step),primary),
            uncorrected_score=(max(abs(g-d) for g,d in zip(target,desired)),
                               sum((g-d)**2 for g,d in zip(target,desired)),abs(step),primary)))
    if not candidates:raise ValueError('No candidate within tested command range and limits')
    best=min(candidates,key=lambda c:c['score'])
    if best['score'][0]>2:raise ValueError('Desired endpoint unsupported within two predicted counts')
    if any(abs(p-b)<2 for p,b in zip(best['models']['stateful_band'],current_positions)):
        raise ValueError('Selected candidate lacks clear predicted motion')
    baseline=min(candidates,key=lambda c:c['uncorrected_score'])
    return dict(schema='rocell.stateful_pair_compensation.v1',
        frozen_model_sha256=frozen['sha256'],current_goals=list(current_goals),
        current_positions=list(current_positions),desired=list(desired),
        proposed_goals=best['target'],predictions=best['models'],predicted_error=best['predicted_error'],
        uncompensated_coupled_goals=baseline['target'],
        uncompensated_predicted_error=[p-d for p,d in zip(baseline['models']['stateful_band'],desired)],
        candidate_count=len(candidates),tested_primary_range=[low,high],
        compensation_is_hypothetical=True,hardware_access=False,movement_authorized=False,
        physical_accuracy_verified=False,interpolation_is_not_validation=True)
