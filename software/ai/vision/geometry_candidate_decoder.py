"""Synthetic geometry-only research decoder; no calibration or admission."""
import itertools,math
import numpy as np
LOCAL=np.array([[-157.5,-73.5],[157.5,-73.5],[157.5,73.5],[-157.5,73.5]])

def fit_pose(points):
    points=np.asarray(points,dtype=float);center=points.mean(0);b=points-center
    angle=math.atan2(np.sum(LOCAL[:,0]*b[:,1]-LOCAL[:,1]*b[:,0]),np.sum(LOCAL*b))
    c,s=math.cos(angle),math.sin(angle);pred=LOCAL@np.array([[c,s],[-s,c]])+center
    return (float(center[0]),float(center[1]),angle),float(np.mean(np.sum((pred-points)**2,axis=1)))

def decode(probabilities):
    candidates=[];strengths=[]
    yy,xx=np.mgrid[:48,:64]
    for q in probabilities:
        first=int(q.argmax());x,y=first%64,first//64
        rival=np.where(((xx-x)*4)**2+((yy-y)*4)**2>64,q,-1).argmax()
        indices=[first,int(rival)]
        candidates.append([[k%64*4*610/256,k//64*4*457/192] for k in indices])
        strengths.append([float(q.flat[k]) for k in indices])
    best=None
    for choice in itertools.product(range(2),repeat=4):
        pose,residual=fit_pose([candidates[i][k] for i,k in enumerate(choice)])
        # Fixed scale:4mm geometric residual plus mean negative log probability.
        cost=residual/16-np.mean([math.log(max(strengths[i][k],1e-12)) for i,k in enumerate(choice)])
        if best is None or cost<best[0]:best=(float(cost),pose,choice,residual)
    return dict(pose=best[1],choice=list(best[2]),residual_mm2=best[3],cost=best[0])
