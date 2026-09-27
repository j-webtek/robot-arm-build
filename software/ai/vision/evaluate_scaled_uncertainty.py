"""Fixed image-dependent bound calibration and independent confirmation."""
import hashlib,json,sys
from pathlib import Path
AI=Path(__file__).resolve().parents[1];ROOT=AI.parents[1];sys.path[:0]=[str(AI),str(AI.parent/'src')]
import numpy as np
import torch
from vision.image_scale_export import validate,predict_image
from vision.linear_residual_pose import LinearResidualPoseNet
from vision.landmark_occlusions import render_controlled
from vision.synthetic_keyboard import catalog_for_workspace
from vision.evaluate_dark_only_normalization import normalize
from vision.train_pose import _pose_from_prediction
from vision.diagnose_pose_tail import decompose
from vision.evaluate_grouped_uncertainty import calibrate,wilson


def summarize(rows,q,tolerance):
    accepted=[r for r in rows if q is not None and q*r['scale_mm']<=tolerance]
    violation=lambda r:q is not None and r['error_mm']>q*r['scale_mm']
    seeds={r['seed'] for r in rows};bad={r['seed'] for r in rows if violation(r)};accepted_seeds={r['seed'] for r in accepted};accepted_bad={r['seed'] for r in accepted if violation(r)}
    return dict(images=len(rows),scenes=len(seeds),covered_scenes=len(seeds-bad),scene_coverage=len(seeds-bad)/len(seeds),scene_wilson95=wilson(len(seeds-bad),len(seeds)),image_coverage=sum(not violation(r) for r in rows)/len(rows),accepted_images=len(accepted),accepted_fraction=len(accepted)/len(rows),accepted_bound_violations=sum(violation(r) for r in accepted),accepted_errors_over_3=sum(r['error_mm']>tolerance for r in accepted),scenes_with_acceptance=len(accepted_seeds),accepted_scenes_with_bound_violation=len(accepted_bad),accepted_scene_violation_wilson95=wilson(len(accepted_bad),len(accepted_seeds)) if accepted_seeds else None)


def run():
    p=AI/'eval/scaled_uncertainty_v1_plan.json';plan=json.loads(p.read_text())
    for f,h in plan['file_sha256'].items():
        if hashlib.sha256((ROOT/f).read_bytes()).hexdigest()!=h:raise ValueError('source mismatch: '+f)
    out=AI/'eval/scaled_uncertainty_v1_report.json'
    if out.exists():raise FileExistsError(out)
    scale=validate(json.loads((ROOT/plan['scale_artifact']).read_text()));assert scale['pose_sha256']==plan['file_sha256'][plan['pose_artifact']]
    assert scale['feature_source_sha256']==plan['file_sha256']['software/ai/vision/image_quality_scale.py']
    torch.set_num_threads(4);pose=LinearResidualPoseNet.from_export(torch.load(ROOT/plan['pose_artifact'],map_location='cpu',weights_only=True));catalog=catalog_for_workspace(ROOT)
    cohorts={}
    for name in ['calibration','confirmation']:
        pixels=[];meta=[];start,count=plan['groups'][name]
        for seed in range(start,start+count):
            for c in plan['conditions']:
                image,label,_=render_controlled(seed,catalog,c,'ellipse');s=predict_image(scale,image);image,_=normalize(image)
                pixels.append(np.asarray(image.resize((128,96))).transpose(2,0,1).copy());meta.append((seed,c,s,label['pose']))
        pixels=np.stack(pixels);x=torch.from_numpy(pixels).float()/255
        with torch.no_grad():prediction=torch.cat([pose(b) for b in x.split(64)]).numpy()
        rows=[dict(seed=s,condition=c,scale_mm=float(scale_value),error_mm=decompose(_pose_from_prediction(v),truth,catalog.keyboard_targets.values())['maximum_mm']) for v,(s,c,scale_value,truth) in zip(prediction,meta)]
        scores=[dict(seed=s,normalized_max=max(r['error_mm']/r['scale_mm'] for r in rows if r['seed']==s)) for s in range(start,start+count)]
        cohorts[name]=dict(rows=rows,scene_scores=scores,pixels_sha256=hashlib.sha256(pixels.tobytes()).hexdigest(),prediction_sha256=hashlib.sha256(prediction.tobytes()).hexdigest())
        if name=='calibration':rank,q=calibrate([r['normalized_max'] for r in scores],plan['alpha']);print('rank',rank,'q',q,flush=True)
        else:
            cohorts[name]['summary']=summarize(rows,q,plan['tolerance_mm'])
            cohorts[name]['conditions']={c:summarize([r for r in rows if r['condition']==c],q,plan['tolerance_mm']) for c in plan['conditions']}
    summary=cohorts['confirmation']['summary'];passed=summary['scene_coverage']>=1-plan['alpha'] and summary['accepted_fraction']>0
    result=dict(plan_sha256=hashlib.sha256(p.read_bytes()).hexdigest(),rank=rank,normalized_quantile=q,cohorts=cohorts,passed=passed,calibration_fits=1,scale_fits=0,pose_fits=0,hardware_writes=0,physical_movements=0,qualification_installed=False,limitations=['Synthetic marginal scene coverage does not guarantee conditional coverage among accepted images.','Fixed3mm research tolerance is not a physical contact margin.','Both calibration and confirmation ranges are consumed; no fitting or tuning during confirmation.','No runtime installation, motion batch or physical qualification.'])
    out.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n');print(json.dumps(dict(summary=summary,conditions=cohorts['confirmation']['conditions'],passed=passed),indent=2))
if __name__=='__main__':run()
