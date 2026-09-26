"""Fixed Huber IRLS rigid fit; no confidence or hardware authority."""
import math
import numpy as np
from vision.geometry_candidate_decoder import LOCAL,fit_pose

def robust_fit(points):
    points=np.asarray(points,dtype=float)
    if points.shape!=(4,2) or not np.isfinite(points).all():raise ValueError('Expected four finite points')
    pose,_=fit_pose(points)
    for _ in range(5):
        c,s=math.cos(pose[2]),math.sin(pose[2]);rotation=np.array([[c,s],[-s,c]])
        residual=np.linalg.norm(LOCAL@rotation+pose[:2]-points,axis=1)
        w=np.minimum(1,3/np.maximum(residual,1e-12));w/=w.sum()
        ac=(LOCAL*w[:,None]).sum(0);bc=(points*w[:,None]).sum(0);a=LOCAL-ac;b=points-bc
        angle=math.atan2(np.sum(w*(a[:,0]*b[:,1]-a[:,1]*b[:,0])),np.sum(w[:,None]*a*b))
        c,s=math.cos(angle),math.sin(angle);center=bc-ac@np.array([[c,s],[-s,c]])
        pose=(float(center[0]),float(center[1]),angle)
    return pose
