"""Sample independent joint progress; stress scenarios are not physical bounds."""
import itertools
import math
from .wrist_tip_review import modeled_tip


def review_response_envelope(model,start,target,*,extra_steps=0,bound_mm=6):
    if type(extra_steps) is not int or not 0<=extra_steps<=2:
        raise ValueError('Explicit zero/one/two-step stress scenario required')
    if type(bound_mm) not in (float,int) or not math.isfinite(bound_mm) or bound_mm<=0:
        raise ValueError('Positive finite model bound required')
    origin=modeled_tip(model,start);modeled_tip(model,target)
    indices=[i for i,(a,b) in enumerate(zip(start,target)) if abs(b-a)>1e-7]
    if len(indices)>3:raise ValueError('Review supports at most three changing joints')
    end=list(target)
    for i in indices:end[i]+=math.copysign(extra_steps*2*math.pi/4096,target[i]-start[i])
    maximum=0.;worst=list(start);count=0
    # Eleven independent progress fractions include each joint's start/end.
    # Grid samples are not a proof of the continuous reachable set.
    for fractions in itertools.product(range(11),repeat=len(indices)):
        q=list(start)
        for i,f in zip(indices,fractions):q[i]=start[i]+(end[i]-start[i])*f/10
        distance=math.dist(origin,modeled_tip(model,q));count+=1
        if distance>maximum:maximum=distance;worst=q
    return dict(schema='rocell.asynchronous_response_review.v1',
        status='SAMPLED_MODEL_BOUND_EXCEEDED' if maximum>bound_mm else 'NO_SAMPLED_EXCEEDANCE',
        changing_joint_indices=indices,extra_nominal_encoder_steps=extra_steps,
        maximum_sampled_tip_displacement_mm=maximum,worst_sample_joints_rad=worst,
        sample_count=count,bound_mm=bound_mm,motion_authorized=False,
        continuous_bound_verified=False,actuator_error_bound_verified=False,
        physical_accuracy_verified=False,tool_offset_hand_tcp_z_mm=-100)
