"""Fixed local centroid after frozen candidate selection; synthetic research."""
import numpy as np
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
    return dict(pose=pose,choice=original['choice'],residual_mm2=residual,original_pose=original['pose'])
