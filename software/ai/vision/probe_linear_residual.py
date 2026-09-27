"""Fixed regularized linear diagnostic; training-only statistics and fitting."""
import hashlib,json,math,sys
from pathlib import Path
AI=Path(__file__).resolve().parents[1];ROOT=AI.parents[1];sys.path[:0]=[str(AI),str(AI.parent/'src')]
import numpy as np
import torch
from vision.mask_conditioned_pose import MaskConditionedPoseNet
from vision.landmark_occlusions import render_controlled
from vision.synthetic_keyboard import catalog_for_workspace
from vision.evaluate_dark_only_normalization import normalize
from vision.train_pose import _pose_from_prediction
from vision.diagnose_pose_tail import decompose


def fit_ridge(features,residual,alpha):
    x=torch.as_tensor(features,dtype=torch.float64);y=torch.as_tensor(residual,dtype=torch.float64)
    if x.ndim!=2 or y.shape!=(len(x),3) or len(x)<2 or not math.isfinite(alpha) or alpha<=0:
        raise ValueError('invalid fit inputs')
    if not torch.isfinite(x).all() or not torch.isfinite(y).all():raise ValueError('nonfinite inputs')
    mean=x.mean(0);std=x.std(0,unbiased=False);constant=std<1e-8;scale=torch.where(constant,torch.ones_like(std),std)
    z=(x-mean)/scale;intercept=y.mean(0);centered=y-intercept
    covariance=z.T@z/len(x);matrix=covariance+alpha*torch.eye(x.shape[1],dtype=x.dtype);rhs=z.T@centered/len(x)
    weights=torch.linalg.solve(matrix,rhs);eigen=torch.linalg.eigvalsh(matrix)
    return dict(mean=mean.tolist(),scale=scale.tolist(),weights=weights.tolist(),intercept=intercept.tolist(),alpha=alpha,
        constant_columns=int(constant.sum()),regularized_condition_number=float(eigen[-1]/eigen[0]),
        normal_equation_max_residual=float((matrix@weights-rhs).abs().max()))


def predict_ridge(fit,features):
    x=np.asarray(features,dtype=np.float64)
    if x.ndim!=2 or x.shape[1]!=len(fit['mean']) or not np.isfinite(x).all():raise ValueError('invalid inference features')
    return ((x-np.array(fit['mean']))/np.array(fit['scale']))@np.array(fit['weights'])+np.array(fit['intercept'])


def run():
    p=AI/'eval/linear_residual_v0_plan.json';plan=json.loads(p.read_text())
    for f,h in plan['file_sha256'].items():
        if hashlib.sha256((ROOT/f).read_bytes()).hexdigest()!=h:raise ValueError('frozen artifact mismatch: '+f)
    out=AI/'eval/linear_residual_v0_report.json'
    if out.exists():raise FileExistsError(out)
    torch.set_num_threads(4);catalog=catalog_for_workspace(ROOT)
    def samples(start,count,style):
        pixels=[];truth=[];meta=[]
        for seed in range(start,start+count):
            for c in plan['conditions']:
                image,label,_=render_controlled(seed,catalog,c,style);image,_=normalize(image);pose=label['pose']
                pixels.append(np.asarray(image.resize((128,96))).transpose(2,0,1).copy());meta.append((seed,c,pose))
                truth.append([(pose[0]-235)/30,(pose[1]-154)/24,(pose[2]-math.pi)/.2])
        return torch.from_numpy(np.stack(pixels)),np.asarray(truth),meta
    sets=dict(training=samples(*plan['training_groups'],'rectangle'),development=samples(*plan['development_groups'],'ellipse'))
    def score(pred,meta):
        rows=[dict(condition=c,**decompose(_pose_from_prediction(v),pose,catalog.keyboard_targets.values())) for v,(_,c,pose) in zip(pred,meta)]
        return {c:dict(mean_mm=float(np.mean([r['mean_mm'] for r in rows if r['condition']==c])),tail=sum(r['maximum_mm']>3 for r in rows if r['condition']==c),yaw_p95=float(np.percentile([r['yaw_degrees'] for r in rows if r['condition']==c],95))) for c in plan['conditions']}
    pose=torch.load(ROOT/plan['checkpoint'],weights_only=True,map_location='cpu');runs=[];splits={}
    for item in plan['representations']:
        model=MaskConditionedPoseNet(item['mode']).eval();model.load_sources(pose,torch.load(ROOT/item['head'],weights_only=True,map_location='cpu'))
        descriptors={};bases={}
        for name,(x,truth,meta) in sets.items():
            fs=[];bs=[]
            with torch.no_grad():
                for batch in x.split(64):
                    f=model.backbone.features[:4](batch.float()/255);m=model.segmentation(f).sigmoid()
                    if item['mode']=='constant':m=torch.ones_like(m)
                    fs.append(model.descriptor(f,m));bs.append(model.backbone.head(model.backbone.features[4:](f)))
            descriptors[name]=torch.cat(fs).numpy();bases[name]=torch.cat(bs).numpy()
        residual=sets['training'][1]-bases['training'];offset=residual.mean(axis=0)
        fit=fit_ridge(descriptors['training'],residual,plan['alpha']);metrics={}
        for name,(x,truth,meta) in sets.items():
            pred=bases[name]+predict_ridge(fit,descriptors[name])
            metrics[name]=dict(normalized_pose_mse=float(np.mean((pred-truth)**2)),score=score(pred,meta),
                descriptor_sha256=hashlib.sha256(descriptors[name].tobytes()).hexdigest(),predictions_sha256=hashlib.sha256(pred.tobytes()).hexdigest())
            if name not in splits:
                splits[name]=dict(images=len(x),pixels_sha256=hashlib.sha256(x.numpy().tobytes()).hexdigest(),baseline_score=score(bases[name],meta),offset_score=score(bases[name]+offset,meta),baseline_mse=float(np.mean((bases[name]-truth)**2)),offset_mse=float(np.mean((bases[name]+offset-truth)**2)))
        runs.append(dict(name=item['name'],fit=fit,splits=metrics));print(item['name'],{k:dict(mse=v['normalized_pose_mse'],tails=sum(c['tail'] for c in v['score'].values())) for k,v in metrics.items()},flush=True)
    for run in runs[1:]:
        checks={}
        for ref,summary in [('baseline',splits['development']['baseline_score']),('control',runs[0]['splits']['development']['score'])]:
            candidate=run['splits']['development']['score']
            checks[ref]={c:dict(mean=candidate[c]['mean_mm']<=summary[c]['mean_mm'],tail=candidate[c]['tail']<=summary[c]['tail'],yaw=candidate[c]['yaw_p95']<=1.1*summary[c]['yaw_p95']) for c in plan['conditions']}
            checks[ref]['occlusion_tail_improves']=sum(candidate[c]['tail'] for c in ['partial','full'])<sum(summary[c]['tail'] for c in ['partial','full'])
        run['checks']=checks;run['passed']=all(all(all(v.values()) if isinstance(v,dict) else v for v in ref.values()) for ref in checks.values())
    result=dict(plan_sha256=hashlib.sha256(p.read_bytes()).hexdigest(),training_offset_normalized=offset.tolist(),splits=splits,runs=runs,
        closed_form_fits=len(runs),optimizer_updates=0,hardware_writes=0,physical_movements=0,qualification_installed=False,
        limitations=['Four training-only closed-form fits; this is model fitting despite zero gradient optimizer updates',
        'Single fixed alpha0.01, normalized pose MSE plus ridge; differs from anchored nonlinear key loss',
        'One shared deterministic control; three candidates vary inherited mask head, not random linear optimizer seed',
        'Reused synthetic development; no regularization selection, new holdout, physical data or runtime correction'])
    out.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n');print('passes',[r['passed'] for r in runs[1:]],'baseline tails',sum(v['tail'] for v in splits['development']['baseline_score'].values()))
if __name__=='__main__':run()
