"""Fixed local centroid after frozen candidate selection; synthetic research."""
import numpy as np
import math
from vision.geometry_candidate_decoder import LOCAL
from vision.geometry_candidate_decoder import decode,fit_pose

def refine(probabilities):
    original=decode(probabilities);points=[];yy,xx=np.mgrid[:48,:64]
    for i,q in enumerate(probabilities):
        first=int(q.argmax());x,y=first%64,first//64
        rival=int(np.where(((xx-x)*4)**2+((yy-y)*4)**2>64,q,-1).argmax())
        index=[first,rival][original['choice'][i]];x,y=index%64,index//64
        mask=(abs(xx-x)<=1)&(abs(yy-y)<=1);weights=np.where(mask,q,0);total=weights.sum()
        points.append([float((weights*xx).sum()/total)*4*610/256,float((weights*yy).sum()/total)*4*457/192])
    pose,residual=fit_pose(points)
    return dict(points=points,pose=pose,choice=original['choice'],residual_mm2=residual,original_pose=original['pose'])


def weighted_fit(points,visibility):
    points=np.asarray(points,dtype=float);v=np.asarray(visibility,dtype=float)
    if points.shape!=(4,2) or v.shape!=(4,) or not np.isfinite(points).all() or not np.isfinite(v).all() or np.any((v<0)|(v>1)):raise ValueError('invalid observation')
    supported=v>=.5
    if supported.sum()<3:return None
    weights=np.where(supported,v,0);weights/=weights.sum()
    a_center=(LOCAL*weights[:,None]).sum(0);b_center=(points*weights[:,None]).sum(0)
    a=LOCAL-a_center;b=points-b_center
    angle=math.atan2(np.sum(weights*(a[:,0]*b[:,1]-a[:,1]*b[:,0])),np.sum(weights[:,None]*a*b))
    c,s=math.cos(angle),math.sin(angle);rotation=np.array([[c,s],[-s,c]])
    center=b_center-a_center@rotation
    return (float(center[0]),float(center[1]),angle)
