"""Offline characterization policy and draft manifest; no hardware authority.

Pose inputs must be decoded and command-correlated by the future owner. Accuracy
is separate from eligibility to consider another leg; eligibility never dispatches.
"""
from .compensated_shoulder_contract import Pose
from .local_pair_offset import pair


def draft_manifest(anchor_goals, *, pattern='legacy'):
    """Offline drafts only; actual preparation also checks fresh measured travel.

    The matched pattern visits anchor-8 three times from each direction.
    Repositioning legs remain measured and checked, not skipped as setup.
    """
    anchor=pair(anchor_goals)
    if sum(anchor)!=4114:raise ValueError('Reviewed shoulder coupling required')
    patterns = {
        'legacy': (-8,0,-16,0)*3,
        'matched': (-8,0,-16,-8,0,-8,-16,-8,0,-8,-16,-8),
        'smoke': (-8,),
    }
    if pattern not in patterns:raise ValueError('Unknown offline campaign pattern')
    legs=[]
    for index, offset in enumerate(patterns[pattern]):
        goals=pair((anchor[0]+offset,anchor[1]-offset))
        legs.append(dict(leg_id=index+1,repeat=index//4+1,command_goals=list(goals),
                         speed=20,acceleration=1,maximum_packets=1))
    return dict(schema='rocell.shoulder_characterization_draft.v1',legs=legs,
                compensation_enabled=False,simulation_only=True,movement_authorized=False)


def assess_leg(before, goals, samples, *, bounds, delivery_confirmed, export_verified):
    """Classify an already observed simulated leg; never relax an envelope.

Bounds are seven absolute count intervals, independently reviewed by the caller.
The provisional 12-count residual ceiling is distinct from 2-count accuracy.
"""
    def outcome(status,reason,**data):
        return dict(status=status,reason=reason,continuation_eligible=status!='STOP',
                    movement_authorized=False,**data)
    if delivery_confirmed is not True:return outcome('STOP','DELIVERY_UNCERTAIN')
    if export_verified is not True:return outcome('STOP','EXPORT_UNVERIFIED')
    try:
        goals=pair(goals)
        if type(before) is not Pose or type(samples) not in (list,tuple) or not 3<=len(samples)<=64:
            raise ValueError('Bounded pose observations required')
        before.validate(before.finished_us)
        if any(before.moving) or sum(goals)!=sum(before.goals[1:3]) or sum(goals)!=4114:
            raise ValueError('Unstable baseline or changed coupling')
        if (type(bounds) not in (list,tuple) or len(bounds)!=7 or
            any(type(b) not in (list,tuple) or len(b)!=2 or any(type(v) is not int for v in b)
                or not 0<=b[0]<=b[1]<=4095 for b in bounds)):
            raise ValueError('Absolute bounds required')
        if any(not lo<=p<=hi for p,(lo,hi) in zip(before.positions,bounds)):
            raise ValueError('Baseline outside bounds')
        if any(not bounds[i][0]<=goals[i-1]<=bounds[i][1] for i in (1,2)):
            raise ValueError('Requested goals outside bounds')
        delta=[g-old for g,old in zip(goals,before.goals[1:3])]
        if not delta[0] or delta[0]!=-delta[1] or max(map(abs,delta))>24:
            raise ValueError('Bounded paired goal change required')
        if any(abs(g-p)>32 for g,p in zip(goals,before.positions[1:3])):
            raise ValueError('Actual-to-goal travel exceeded')
        last=before.finished_us
        for sample in samples:
            if type(sample) is not Pose:raise ValueError('Invalid sample')
            sample.validate(sample.finished_us)
            if sample.started_us<=last or sample.started_us-last>1000000 or sample.finished_us-before.finished_us>8000000:
                raise ValueError('Out-of-order or expired observation')
            last=sample.finished_us
            for i in range(7):
                selected=i in (1,2);expected=goals[i-1] if selected else before.goals[i]
                lo,hi=bounds[i]
                if sample.goals[i]!=expected or not lo<=sample.positions[i]<=hi:
                    raise ValueError('Goal readback or absolute bounds')
                change=sample.positions[i]-before.positions[i]
                if selected:
                    if abs(change)>32 or change*(1 if delta[i-1]>0 else -1)<-1:
                        raise ValueError('Unexpected direction or excessive travel')
                elif abs(change)>2 or sample.moving[i]:
                    raise ValueError('Neighbor changed')
        tail=samples[-3:]
        if (any(any(p.moving) for p in tail) or tail[-1].finished_us-tail[0].finished_us<200000 or
            any(abs(p.positions[i]-tail[0].positions[i])>1 for p in tail for i in range(7))):
            return outcome('STOP','NOT_SETTLED')
        final=tail[-1].positions
        actual_delta=[final[i]-before.positions[i] for i in (1,2)]
        if any(abs(d)<2 for d in actual_delta):return outcome('STOP','NO_CLEAR_RESPONSE')
        residual=[final[i]-goals[i-1] for i in (1,2)]
        if max(map(abs,residual))>12:return outcome('STOP','RESIDUAL_ENVELOPE_EXCEEDED')
        status='SETTLED_ACCURATE' if max(map(abs,residual))<=2 else 'SETTLED_MISS'
        return outcome(status,'MEASUREMENT_RETAINED',actual_delta=actual_delta,
                       goal_delta=delta,endpoint_error=residual,final_positions=list(final))
    except (ValueError,TypeError,AttributeError):
        return outcome('STOP','INVALID_OR_UNSAFE_EVIDENCE')
