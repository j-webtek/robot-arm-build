"""Grouped training-only scale feasibility; no calibrated admission."""
import hashlib,json,sys
from pathlib import Path
AI=Path(__file__).resolve().parents[1];ROOT=AI.parents[1];sys.path[:0]=[str(AI),str(AI.parent/'src')]
import numpy as np
import torch
from vision.image_quality_scale import features,fit_scale,predict_scale
from vision.audit_scene_splits import group_folds
from vision.linear_residual_pose import LinearResidualPoseNet
from vision.landmark_occlusions import render_controlled
from vision.synthetic_keyboard import catalog_for_workspace
from vision.evaluate_dark_only_normalization import normalize
from vision.train_pose import _pose_from_prediction
from vision.diagnose_pose_tail import decompose


def run():
    p=AI/'train/image_quality_scale_v1_plan.json';plan=json.loads(p.read_text())
    for f,h in plan['file_sha256'].items():
        if hashlib.sha256((ROOT/f).read_bytes()).hexdigest()!=h:raise ValueError('source mismatch: '+f)
    out=AI/'eval/image_quality_scale_v1_report.json'
    if out.exists():raise FileExistsError(out)
    torch.set_num_threads(4);model=LinearResidualPoseNet.from_export(torch.load(ROOT/plan['artifact'],map_location='cpu',weights_only=True));catalog=catalog_for_workspace(ROOT)
    pixels=[];quality=[];meta=[]
    start,count=plan['groups']
    for seed in range(start,start+count):
        for style in plan['styles']:
            for c in plan['conditions']:
                image,label,_=render_controlled(seed,catalog,c,style);quality.append(features(image));image,_=normalize(image)
                pixels.append(np.asarray(image.resize((128,96))).transpose(2,0,1).copy());meta.append(dict(seed=seed,style=style,condition=c,truth=label['pose']))
    pixels=np.stack(pixels);quality=np.stack(quality);x=torch.from_numpy(pixels).float()/255
    with torch.no_grad():prediction=torch.cat([model(b) for b in x.split(64)]).numpy()
    errors=np.array([decompose(_pose_from_prediction(v),m['truth'],catalog.keyboard_targets.values())['maximum_mm'] for v,m in zip(prediction,meta)])
    folds=group_folds(range(start,start+count));oof=np.empty(len(meta));constant=np.empty(len(meta));fits=[];seen=np.zeros(len(meta),int)
    for i,fold in enumerate(folds):
        mask=np.array([m['seed'] in fold for m in meta]);fit=fit_scale(quality[~mask],errors[~mask],plan['alpha'])
        oof[mask]=predict_scale(fit,quality[mask]);constant[mask]=np.clip(np.exp(fit['intercept']),.1,20);seen[mask]+=1
        fits.append(dict(fold=i,validation_seeds=fold,training_rows=int((~mask).sum()),validation_rows=int(mask.sum()),fit=fit))
    assert np.all(seen==1)
    rows=[dict(seed=m['seed'],style=m['style'],condition=m['condition'],error_mm=float(e),scale_mm=float(v),constant_scale_mm=float(b)) for m,e,v,b in zip(meta,errors,oof,constant)]
    summaries={}
    for c in plan['conditions']:
        idx=np.array([m['condition']==c for m in meta]);truth=np.log(errors[idx]+.1)
        summaries[c]=dict(images=int(idx.sum()),scale_log_mse=float(np.mean((np.log(oof[idx])-truth)**2)),constant_log_mse=float(np.mean((np.log(constant[idx])-truth)**2)))
    passed=all(v['scale_log_mse']<v['constant_log_mse'] for v in summaries.values())
    result=dict(plan_sha256=hashlib.sha256(p.read_bytes()).hexdigest(),pixel_sha256=hashlib.sha256(pixels.tobytes()).hexdigest(),features_sha256=hashlib.sha256(quality.tobytes()).hexdigest(),prediction_sha256=hashlib.sha256(prediction.tobytes()).hexdigest(),fold_fits=fits,rows=rows,summaries=summaries,passed=passed,uncertainty_fits=5,pose_fits=0,calibration_fits=0,hardware_writes=0,physical_movements=0,qualification_installed=False,limitations=['Scale predicts error plus0.1, not an upper bound or confidence.','Training-only grouped cross-validation on new uncertainty-training scenes; no calibration or confirmation.','Image statistics can reflect synthetic shortcuts; no physical camera validation.','Fixed ridge alpha1.0 and feature set, no grid search or runtime installation.'])
    out.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n');print(json.dumps(dict(summaries=summaries,passed=passed),indent=2))
if __name__=='__main__':run()
