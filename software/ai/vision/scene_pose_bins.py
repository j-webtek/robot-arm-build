"""Closed-support pose bins; retains frozen v0 audit implementation separately."""
import math
import numpy as np

def pose_bins(poses):
    poses=np.asarray(poses,dtype=float)
    lower=np.array([205.,130.,math.pi-math.radians(11)])
    upper=np.array([265.,178.,math.pi+math.radians(11)])
    if poses.ndim!=2 or poses.shape[1]!=3 or not np.isfinite(poses).all() or np.any(poses<lower) or np.any(poses>upper):
        raise ValueError('pose outside fixed support')
    cells=np.minimum(((poses-lower)/(upper-lower)*5).astype(int),4)
    return (cells[:,0]*25+cells[:,1]*5+cells[:,2]).tolist()
