"""Frozen training-scene cross-validation; no final fit or holdout execution."""
import hashlib,json,math,sys
from pathlib import Path
AI=Path(__file__).resolve().parents[1];ROOT=AI.parents[1];sys.path[:0]=[str(AI),str(AI.parent/'src')]
import numpy as np
import torch
from vision.pose_model import KeyboardPoseNet
from vision.landmark_occlusions import render_controlled
from vision.synthetic_keyboard import catalog_for_workspace
from vision.evaluate_dark_only_normalization import normalize
from vision.train_pose import _pose_from_prediction
from vision.diagnose_pose_tail import decompose
from vision.probe_linear_residual import fit_ridge,predict_ridge
from vision.evaluate_linear_fresh import checks_for


def select_candidate(runs):
    eligible=[r for r in runs if r['passed']]
    return min(eligible,key=lambda r:(sum(v['tail'] for v in r['summary'].values()),np.mean([v['mean_mm'] for v in r['summary'].values()]),-r['alpha']))['alpha'] if eligible else None


def fold_indices(seeds,validation):
    seeds=np.asarray(seeds);validation=set(validation)
    mask=np.array([int(s) in validation for s in seeds])
    if not mask.any() or mask.all():raise ValueError('empty fit or validation population')
    return np.flatnonzero(~mask),np.flatnonzero(mask)


def run():
    path=AI/'train/grouped_linear_v1_plan.json';plan=json.loads(path.read_text())
    for f,h in plan['file_sha256'].items():
        if hashlib.sha256((ROOT/f).read_bytes()).hexdigest()!=h:raise ValueError('source mismatch: '+f)
    out=AI/'eval/grouped_linear_v1_report.json'
    if out.exists():raise FileExistsError(out)
    protocol=json.loads((ROOT/plan['protocol']).read_text());torch.set_num_threads(4)
    model=KeyboardPoseNet().eval();model.load_state_dict(torch.load(ROOT/plan['checkpoint'],weights_only=True,map_location='cpu'))
    catalog=catalog_for_workspace(ROOT);conditions=protocol['conditions'];start,end=protocol['training_seed_range'];sets={}
    for style in [protocol['fit_style'],protocol['validation_style']]:
        pixels=[];truth=[];meta=[]
        for seed in range(start,end+1):
            for c in conditions:
                image,label,_=render_controlled(seed,catalog,c,style);image,_=normalize(image);pose=label['pose']
                pixels.append(np.asarray(image.resize((128,96))).transpose(2,0,1).copy())
                truth.append([(pose[0]-235)/30,(pose[1]-154)/24,(pose[2]-math.pi)/.2]);meta.append((seed,c,pose))
        pixels=np.stack(pixels);features=[];bases=[]
        with torch.no_grad():
            for batch in torch.from_numpy(pixels).split(64):
                f=model.features[:4](batch.float()/255)
                features.append(torch.nn.functional.adaptive_avg_pool2d(f,(4,4)).flatten(1));bases.append(model.head(model.features[4:](f)))
        sets[style]=dict(features=torch.cat(features).numpy(),base=torch.cat(bases).numpy(),truth=np.array(truth),meta=meta,pixels_sha256=hashlib.sha256(pixels.tobytes()).hexdigest())
        print('rendered',style,len(meta),flush=True)
    train=sets[protocol['fit_style']];val=sets[protocol['validation_style']]
    assert train['meta']==val['meta']
    seeds=[v[0] for v in train['meta']];runs=[]
    def score(pred):
        rows=[dict(seed=s,condition=c,**decompose(_pose_from_prediction(p),t,catalog.keyboard_targets.values())) for p,(s,c,t) in zip(pred,val['meta'])]
        summary={c:dict(cases=sum(r['condition']==c for r in rows),mean_mm=float(np.mean([r['mean_mm'] for r in rows if r['condition']==c])),tail=sum(r['maximum_mm']>3 for r in rows if r['condition']==c),yaw_p95=float(np.percentile([r['yaw_degrees'] for r in rows if r['condition']==c],95))) for c in conditions}
        return rows,summary
    baseline_rows,baseline=score(val['base'])
    for alpha in protocol['ridge_alphas']:
        prediction=np.empty_like(val['truth']);seen=np.zeros(len(seeds),dtype=int);fits=[]
        for fold,validation in enumerate(protocol['validation_scene_folds']):
            ti,vi=fold_indices(seeds,validation)
            fit=fit_ridge(train['features'][ti],train['truth'][ti]-train['base'][ti],alpha)
            prediction[vi]=val['base'][vi]+predict_ridge(fit,val['features'][vi]);seen[vi]+=1
            fits.append(dict(fold=fold,training_rows=len(ti),validation_rows=len(vi),training_seeds=sorted(set(seeds[i] for i in ti)),validation_seeds=validation,fit=fit))
        assert np.all(seen==1)
        rows,summary=score(prediction);checks,passed=checks_for(baseline,summary)
        runs.append(dict(alpha=alpha,fold_fits=fits,rows=rows,summary=summary,checks=checks,passed=passed,predictions_sha256=hashlib.sha256(prediction.tobytes()).hexdigest()))
        print('alpha',alpha,'tails',sum(v['tail'] for v in summary.values()),'passed',passed,flush=True)
    result=dict(plan_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),pixel_sha256={k:v['pixels_sha256'] for k,v in sets.items()},baseline_rows=baseline_rows,baseline_summary=baseline,runs=runs,selected_alpha=select_candidate(runs),closed_form_fits=20,final_fits=0,hardware_writes=0,physical_movements=0,qualification_installed=False,limitations=['Training-selection data only; all variants grouped by scene. Baseline fixed after prior development selection.','Ellipse training-pool variants are not untouched confirmation. No15M or30M evaluation data loaded.','No final refit, export, physical calibration or runtime promotion. Selection evidence cannot qualify localization.'])
    out.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n');print('selected',result['selected_alpha'],flush=True)
if __name__=='__main__':run()
