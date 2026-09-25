"""Offline six-leg experiment and frozen hypotheses; no transport or signing."""
import copy
import hashlib
import math
from .first_motion_contract import canonical
from .local_pair_offset import pair
from .characterization_admission import encode_manifest


def freeze_models(review):
    """Copy only fitted parameters, not future observations or training logic."""
    if review.get('schema') != 'rocell.matrix_model_review.v1':
        raise ValueError('Reviewed model parameters required')
    models = dict(constant=list(review['constant_residual']),
        directional={str(k): list(v) for k,v in review['directional_residual'].items()},
        bands=copy.deepcopy(review['bands']))
    if set(models['directional']) != {'-1', '1'}:
        raise ValueError('Two directional fits required')
    values=[models['constant'], *models['directional'].values(), *models['bands']]
    if len(models['bands'])!=2 or any(len(v)!=2 or any(
            type(x) not in (int,float) or not math.isfinite(x) or abs(x)>16 for x in v) for v in values):
        raise ValueError('Bounded finite fitted pairs required')
    if any(lo>hi for lo,hi in models['bands']):
        raise ValueError('Ordered bands required')
    return dict(parameters=models,sha256=hashlib.sha256(canonical(models)).hexdigest())


def predict(frozen, *, target, before, direction):
    """One-step endpoint prediction; measured start required when evaluating data."""
    models=frozen['parameters']
    if hashlib.sha256(canonical(models)).hexdigest()!=frozen['sha256']:
        raise ValueError('Frozen model changed')
    target=pair(target)
    if type(direction) is not int or direction not in (-1,1) or len(before)!=2:
        raise ValueError('Direction and starting pair required')
    if any(type(v) not in (int,float) or not math.isfinite(v) or not 0<=v<=4095 for v in before):
        raise ValueError('Finite starting positions required')
    return dict(constant=[g+b for g,b in zip(target,models['constant'])],
        directional=[g+b for g,b in zip(target,models['directional'][str(direction)])],
        stateful_band=[max(g+lo,min(p,g+hi)) for g,p,(lo,hi) in zip(target,before,models['bands'])])


def draft_repeatability(goals, positions, bounds, frozen):
    """Exactly three -12/+12 target pairs; no offset compensation or speed sweep.

    Validate command limits independently of hypotheses. Rollouts below are
    simulated states, never substitutes for native fresh baselines/clearance.
    """
    goals,positions=pair(goals),pair(positions)
    targets=[[goals[0]+offset,goals[1]-offset] for offset in (-12,0)*3]
    manifest=dict(goals=targets,bounds=copy.deepcopy(bounds),maximum_us=60000000)
    # Reuse the actual wire-contract validator without producing a signature.
    encode_manifest(manifest,campaign='00'*32,reference='00'*32)
    if any(not bounds[i+1][0]<=positions[i]<=bounds[i+1][1] for i in range(2)):
        raise ValueError('Measured anchor outside reviewed bounds')
    if any(abs(g-p)>32 for target in targets for g,p in zip(target,positions)):
        raise ValueError('Campaign target exceeds measured-anchor envelope')
    states={name:list(positions) for name in ('constant','directional','stateful_band')}
    legs=[]
    for index,target in enumerate(targets):
        direction=-1 if index%2==0 else 1
        simulations={}
        for name,before in states.items():
            endpoint=predict(frozen,target=target,before=before,direction=direction)[name]
            simulations[name]=dict(simulated_before=before,predicted_endpoint=endpoint,
                predicted_delta=[p-b for p,b in zip(endpoint,before)])
            states[name]=endpoint
        legs.append(dict(leg=index,targets=target,register_delta=[direction*12,-direction*12],
                         speed=20,acceleration=1,simulated_rollouts=simulations))
    return dict(schema='rocell.shoulder_repeatability_plan.v1',manifest=manifest,
        anchor_goals=list(goals),anchor_positions=list(positions),legs=legs,
        frozen_models=copy.deepcopy(frozen),maximum_selected_excursion_counts=32,
        maximum_neighbour_excursion_counts=2,hardware_access=False,movement_authorized=False,
        physical_clearance_verified=False,compensation_enabled=False,
        rollout_is_hypothetical=True,requires_fresh_admission=True,
        current_r37_selector_supports_plan=False)
