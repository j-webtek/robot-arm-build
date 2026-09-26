"""Synthetic-image edge-centroid hypothesis; not measured pixel calibration."""
import math
import numpy as np


def refine(image, point):
    if len(point)!=2 or any(type(v) not in (int,float) or not math.isfinite(v) for v in point):
        raise ValueError('finite XY required')
    gray=np.asarray(image.convert('L'),dtype=np.float64)
    if gray.shape!=(192,256): raise ValueError('requires frozen synthetic projection')
    x,y=point[0]*256/610,point[1]*192/457
    ix,iy=round(x),round(y)
    if ix<5 or iy<5 or ix>=251 or iy>=187: return tuple(point)
    patch=gray[iy-4:iy+5,ix-4:ix+5]
    gy,gx=np.gradient(patch)
    yy,xx=np.mgrid[iy-4:iy+5,ix-4:ix+5]
    weights=np.hypot(gx,gy)*np.exp(-((xx-x)**2+(yy-y)**2)/(2*2.0**2))
    total=float(weights.sum())
    if total<=1e-12: return tuple(point)
    dx=(float((weights*xx).sum())/total-x)*610/256
    dy=(float((weights*yy).sum())/total-y)*457/192
    length=math.hypot(dx,dy)
    scale=min(1.0,1.0/length) if length else 1.0
    return point[0]+dx*scale,point[1]+dy*scale
