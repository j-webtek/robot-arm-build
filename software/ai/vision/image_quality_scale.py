"""Image-only error-scale features; predictions are not calibrated bounds."""
import numpy as np


def features(image):
    if image.mode!='RGB':raise ValueError('RGB required')
    rgb=np.asarray(image.resize((128,96)),dtype=np.float64)/255.
    gray=rgb@np.array([.299,.587,.114])
    gx=np.abs(np.diff(gray,axis=1,append=gray[:,-1:]));gy=np.abs(np.diff(gray,axis=0,append=gray[-1:,:]));edge=(gx+gy)/2
    result=[gray.mean(),gray.std(),np.percentile(gray,5),np.percentile(gray,95),(gray<.1).mean(),(gray>.9).mean(),gx.mean(),gy.mean()]
    for y in range(4):
        for x in range(4):
            tile=gray[y*24:(y+1)*24,x*32:(x+1)*32];e=edge[y*24:(y+1)*24,x*32:(x+1)*32]
            result.extend([tile.mean(),tile.std(),e.mean()])
    return np.asarray(result,dtype=np.float64)


def fit_scale(x,error,alpha=1.):
    x=np.asarray(x,dtype=float);error=np.asarray(error,dtype=float)
    if x.ndim!=2 or x.shape[1]!=56 or error.shape!=(len(x),) or len(x)<2 or not np.isfinite(x).all() or not np.isfinite(error).all() or np.any(error<0) or not np.isfinite(alpha) or alpha<=0:raise ValueError('invalid fit input')
    mean=x.mean(0);scale=x.std(0);scale=np.where(scale<1e-8,1.,scale);z=(x-mean)/scale;y=np.log(error+.1);intercept=y.mean()
    weights=np.linalg.solve(z.T@z/len(z)+alpha*np.eye(56),z.T@(y-intercept)/len(z))
    return dict(mean=mean.tolist(),scale=scale.tolist(),weights=weights.tolist(),intercept=float(intercept),alpha=alpha)


def predict_scale(fit,x):
    x=np.asarray(x,dtype=float)
    if x.ndim!=2 or x.shape[1]!=56 or not np.isfinite(x).all():raise ValueError('invalid features')
    log=((x-np.array(fit['mean']))/np.array(fit['scale']))@np.array(fit['weights'])+fit['intercept']
    return np.exp(np.clip(log,np.log(.1),np.log(20.)))
