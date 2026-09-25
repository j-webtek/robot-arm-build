"""Two-point inverse interpolation hypothesis, scoped to one starting posture.

Zero training residual is inevitable with two points: it is not validation.
No transport access, extrapolation, or motion admission is provided here.
"""
import hashlib
import math
from .first_motion_contract import canonical
from .coordinated_trace_review import review_coordinated_trace


def fit_local_map(reports):
    if len(reports)!=2:
        raise ValueError('Exactly two independent trial reports required')
    points=[];baseline=None;settings=None
    for report in reports:
        run=report['run'];tx=run['transaction'];command=tx['command']
        if run.get('error') is not None or run.get('acknowledgment_received') is not True:
            raise ValueError('Uncertain trial cannot train map')
        if command.get('T')!=101 or command.get('joint')!=4:
            raise ValueError('Single wrist command required')
        start=tx['baseline_joints'];final=tx['rows'][-1][3]
        if len(start)!=6 or len(final)!=6 or any(type(v) not in (int,float) or not math.isfinite(v) for v in [*start,*final,command['rad']]):
            raise ValueError('Finite complete joint evidence required')
        if baseline is None:baseline=list(start);settings=(command['spd'],command['acc'])
        if start!=baseline or (command['spd'],command['acc'])!=settings:
            raise ValueError('Same start and speed/acceleration required')
        if any(abs(a-b)>1e-8 for i,(a,b) in enumerate(zip(start,final)) if i!=3):
            raise ValueError('Cross-joint change is outside map scope')
        review=review_coordinated_trace(report);wrist=review['joints'][3]
        if review['feedback_failures'] or (wrist['unchanged_tail_s'] or 0)<1:
            raise ValueError('Settled uninterrupted feedback required')
        if not start[3]<final[3]<command['rad']:
            raise ValueError('Increasing undershoot trials required')
        points.append(dict(command_rad=command['rad'],reported_rad=final[3]))
    points.sort(key=lambda p:p['command_rad'])
    dx=points[1]['command_rad']-points[0]['command_rad']
    dy=points[1]['reported_rad']-points[0]['reported_rad']
    # Require more than one reference encoder step of separation in both axes.
    if min(dx,dy)<=2*math.pi/4096:
        raise ValueError('Insufficient independent point separation')
    slope=dy/dx
    model=dict(schema='rocell.local_wrist_response_map.v1',
        model='TWO_POINT_MONOTONE_INVERSE_INTERPOLATION',baseline_joints_rad=baseline,
        spd=settings[0],acc=settings[1],points=points,response_slope=slope,
        response_intercept=points[0]['reported_rad']-slope*points[0]['command_rad'],
        held_out_validated=False,physical_accuracy_verified=False,motion_authorized=False)
    return dict(model,model_sha256=hashlib.sha256(canonical(model)).hexdigest())


def predict_command(model, desired_rad):
    unsigned={k:v for k,v in model.items() if k!='model_sha256'}
    if hashlib.sha256(canonical(unsigned)).hexdigest()!=model['model_sha256']:
        raise ValueError('Map changed')
    if type(desired_rad) not in (int,float) or not math.isfinite(desired_rad):
        raise ValueError('Finite desired target required')
    low,high=model['points']
    if not low['reported_rad']<desired_rad<high['reported_rad']:
        raise ValueError('Distinct interior held-out target required; no extrapolation')
    fraction=(desired_rad-low['reported_rad'])/(high['reported_rad']-low['reported_rad'])
    return low['command_rad']+fraction*(high['command_rad']-low['command_rad'])
