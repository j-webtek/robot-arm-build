"""Training-only offset comparator; all corrections remain research diagnostics."""
import hashlib,json,math,sys
from pathlib import Path
AI=Path(__file__).resolve().parents[1];ROOT=AI.parents[1];sys.path[:0]=[str(AI),str(AI.parent/'src')]
import numpy as np
import torch
from vision.pose_model import KeyboardPoseNet
from vision.mask_conditioned_pose import MaskConditionedPoseNet
from vision.landmark_occlusions import render_controlled
from vision.synthetic_keyboard import catalog_for_workspace
from vision.evaluate_dark_only_normalization import normalize
from vision.train_pose import _pose_from_prediction
from vision.diagnose_pose_tail import decompose


def correction_stats(base, prediction, truth):
    base=np.asarray(base,dtype=np.float64);prediction=np.asarray(prediction,dtype=np.float64);truth=np.asarray(truth,dtype=np.float64)
    if base.ndim!=2 or base.shape[1]!=3 or base.shape!=prediction.shape or base.shape!=truth.shape or len(base)<2:
        raise ValueError('expected matching N x3 arrays, N>=2')
    if not all(np.isfinite(a).all() for a in (base,prediction,truth)):raise ValueError('nonfinite poses')
    correction=prediction-base;needed=truth-base
    result={}
    for i,(axis,scale) in enumerate([('x_mm',30),('y_mm',24),('yaw_degrees',math.degrees(.2))]):
        c=correction[:,i]*scale;n=needed[:,i]*scale;centered=c-c.mean();target=n-n.mean();energy=float(np.mean(c*c))
        denominator=float(np.sqrt(np.sum(centered**2)*np.sum(target**2)))
        result[axis]=dict(mean=float(c.mean()),std=float(c.std()),needed_mean=float(n.mean()),needed_std=float(n.std()),
            centered_energy_fraction=float(np.mean(centered**2)/energy) if energy else None,
            correlation=float(np.sum(centered*target)/denominator) if denominator else None,
            residual_mse=float(np.mean((n-c)**2)),baseline_mse=float(np.mean(n*n)),
            centered_residual_mse=float(np.mean((target-centered)**2)))
    return result


def training_offset(base,truth):
    base=np.asarray(base,dtype=np.float64);truth=np.asarray(truth,dtype=np.float64)
    correction_stats(base,base,truth)
    return (truth-base).mean(axis=0)


def run():
    p=AI/'eval/residual_corrections_v0_plan.json';plan=json.loads(p.read_text())
    for f,h in plan['file_sha256'].items():
        if hashlib.sha256((ROOT/f).read_bytes()).hexdigest()!=h:raise ValueError('source mismatch: '+f)
    out=AI/'eval/residual_corrections_v0_report.json'
    if out.exists():raise FileExistsError(out)
    torch.set_num_threads(4);catalog=catalog_for_workspace(ROOT)
    def samples(start,count,style):
        pixels=[];truth=[];metadata=[]
        for seed in range(start,start+count):
            for condition in plan['conditions']:
                image,label,_=render_controlled(seed,catalog,condition,style);image,_=normalize(image);pose=label['pose']
                pixels.append(np.asarray(image.resize((128,96))).transpose(2,0,1).copy());metadata.append((seed,condition,pose))
                truth.append([(pose[0]-235)/30,(pose[1]-154)/24,(pose[2]-math.pi)/.2])
        return torch.from_numpy(np.stack(pixels)),np.array(truth),metadata
    sets=dict(training=samples(*plan['training_groups'],'rectangle'),development=samples(*plan['development_groups'],'ellipse'))
    def predict(model,x):
        with torch.no_grad():return torch.cat([model(b.float()/255) for b in x.split(64)]).numpy()
    def score(pred,metadata):
        rows=[dict(condition=c,**decompose(_pose_from_prediction(row),pose,catalog.keyboard_targets.values())) for row,(_,c,pose) in zip(pred,metadata)]
        return {c:dict(mean_mm=float(np.mean([r['mean_mm'] for r in rows if r['condition']==c])),tails=sum(r['maximum_mm']>3 for r in rows if r['condition']==c)) for c in plan['conditions']}
    baseline=KeyboardPoseNet().eval();baseline.load_state_dict(torch.load(ROOT/plan['checkpoint'],map_location='cpu',weights_only=True))
    bases={name:predict(baseline,x) for name,(x,_,_) in sets.items()}
    offset=training_offset(bases['training'],sets['training'][1])
    splits={}
    for name,(x,truth,meta) in sets.items():
        splits[name]=dict(images=len(x),pixels_sha256=hashlib.sha256(x.numpy().tobytes()).hexdigest(),baseline_predictions_sha256=hashlib.sha256(bases[name].tobytes()).hexdigest(),
            baseline_score=score(bases[name],meta),offset_score=score(bases[name]+offset,meta),offset_stats=correction_stats(bases[name],bases[name]+offset,truth))
    runs=[]
    for item in plan['models']:
        model=MaskConditionedPoseNet.from_export(torch.load(ROOT/item['path'],map_location='cpu',weights_only=True))
        assert model.mode==item['mode']
        record=dict(seed=item['seed'],mode=item['mode'],splits={})
        for name,(x,truth,meta) in sets.items():
            pred=predict(model,x);record['splits'][name]=dict(stats=correction_stats(bases[name],pred,truth),score=score(pred,meta),predictions_sha256=hashlib.sha256(pred.tobytes()).hexdigest())
        runs.append(record);print(item['seed'],item['mode'],record['splits']['development']['stats'],flush=True)
    result=dict(plan_sha256=hashlib.sha256(p.read_bytes()).hexdigest(),training_offset_normalized=offset.tolist(),splits=splits,runs=runs,
        optimizer_updates=0,hardware_writes=0,physical_movements=0,qualification_installed=False,
        limitations=['CPU recomputation of checkpoints trained on GPU; no bitwise historical score assertion',
        'Offset is fitted only on training truth, minimizing unweighted normalized pose MSE; not the anchored key-loss objective',
        'Reused synthetic development, no new holdout; yaw residual uses the bounded local pose range',
        'Correlation and centered energy describe variation, not proof of causal useful learning',
        'No correction, confidence rule or calibration installed at runtime'])
    out.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    print(json.dumps(dict(offset=offset.tolist(),baseline_tails=sum(v['tails'] for v in splits['development']['baseline_score'].values()),offset_tails=sum(v['tails'] for v in splits['development']['offset_score'].values())),indent=2))
if __name__=='__main__':run()
