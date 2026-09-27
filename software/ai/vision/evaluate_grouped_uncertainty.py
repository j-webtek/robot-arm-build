"""Global scene-group calibration and independent synthetic confirmation."""
import hashlib,json,math,sys
from pathlib import Path
AI=Path(__file__).resolve().parents[1];ROOT=AI.parents[1];sys.path[:0]=[str(AI),str(AI.parent/'src')]
import numpy as np
import torch
from vision.linear_residual_pose import LinearResidualPoseNet
from vision.landmark_occlusions import render_controlled
from vision.synthetic_keyboard import catalog_for_workspace
from vision.evaluate_dark_only_normalization import normalize
from vision.train_pose import _pose_from_prediction
from vision.diagnose_pose_tail import decompose


def calibrate(scores,alpha):
    scores=list(scores)
    if not scores or not 0<alpha<1 or any(not math.isfinite(s) or s<0 for s in scores):raise ValueError('invalid calibration scores')
    rank=math.ceil((len(scores)+1)*(1-alpha))
    return rank,sorted(scores)[rank-1] if rank<=len(scores) else None


def wilson(successes,total):
    if total<=0 or not 0<=successes<=total:raise ValueError('invalid binomial counts')
    z=1.959963984540054;p=successes/total;denom=1+z*z/total
    center=(p+z*z/(2*total))/denom;half=z*math.sqrt(p*(1-p)/total+z*z/(4*total*total))/denom
    return [max(0.,center-half),min(1.,center+half)]


def decision(scores,radius,tolerance):
    if tolerance<=0 or not math.isfinite(tolerance) or (radius is not None and (radius<0 or not math.isfinite(radius))):raise ValueError('invalid bound')
    covered=sum(radius is None or s<=radius for s in scores)
    accepted=radius is not None and radius<=tolerance
    return dict(covered=covered,total=len(scores),coverage=covered/len(scores),wilson95=wilson(covered,len(scores)),accepted=accepted,accepted_fraction=float(accepted))


def run():
    path=AI/'eval/grouped_uncertainty_v1_plan.json';plan=json.loads(path.read_text())
    for f,h in plan['file_sha256'].items():
        if hashlib.sha256((ROOT/f).read_bytes()).hexdigest()!=h:raise ValueError('source mismatch: '+f)
    out=AI/'eval/grouped_uncertainty_v1_report.json'
    if out.exists():raise FileExistsError(out)
    torch.set_num_threads(4);model=LinearResidualPoseNet.from_export(torch.load(ROOT/plan['artifact'],map_location='cpu',weights_only=True));catalog=catalog_for_workspace(ROOT)
    assert len(catalog.keyboard_targets)==46
    cohorts={};radius=None
    for name in ['calibration','confirmation']:
        start,count=plan['groups'][name];pixels=[];meta=[]
        for seed in range(start,start+count):
            for c in plan['conditions']:
                image,label,_=render_controlled(seed,catalog,c,'ellipse');image,_=normalize(image)
                pixels.append(np.asarray(image.resize((128,96))).transpose(2,0,1).copy());meta.append((seed,c,label['pose']))
        pixels=np.stack(pixels);x=torch.from_numpy(pixels).float()/255
        with torch.no_grad():pred=torch.cat([model(b) for b in x.split(64)]).numpy()
        rows=[dict(seed=s,condition=c,**decompose(_pose_from_prediction(v),truth,catalog.keyboard_targets.values())) for v,(s,c,truth) in zip(pred,meta)]
        scenes=[dict(seed=s,maximum_mm=max(r['maximum_mm'] for r in rows if r['seed']==s)) for s in range(start,start+count)]
        scores=[r['maximum_mm'] for r in scenes]
        cohorts[name]=dict(rows=rows,scenes=scenes,pixels_sha256=hashlib.sha256(pixels.tobytes()).hexdigest(),predictions_sha256=hashlib.sha256(pred.tobytes()).hexdigest(),maximum_error_mm=max(scores))
        if name=='calibration':
            rank,radius=calibrate(scores,plan['alpha']);print('calibration rank',rank,'radius',radius,flush=True)
        else:
            cohorts[name]['scene_decision']=decision(scores,radius,plan['tolerance_mm'])
            cohorts[name]['image_coverage']=sum(radius is None or r['maximum_mm']<=radius for r in rows)/len(rows)
            cohorts[name]['bound_violations']=[s for s in scenes if radius is not None and s['maximum_mm']>radius]
    d=cohorts['confirmation']['scene_decision'];passed=d['coverage']>=1-plan['alpha'] and d['accepted_fraction']>0
    result=dict(plan_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),artifact_sha256=plan['file_sha256'][plan['artifact']],cohorts=cohorts,rank=rank,radius_mm=radius,infinite_radius=radius is None,passed=passed,calibration_fits=1,new_model_fits=0,hardware_writes=0,physical_movements=0,qualification_installed=False,limitations=['Global radius; research-only3mm tolerance, no physical safe-region margin.','Scene-level Wilson interval is descriptive under binomial assumptions, not a physical coverage guarantee.','Separate synthetic calibration/confirmation; both ranges are now consumed.','Frozen weights and rules; no quality classifier, runtime gate installation or ModelMotionBatch qualification.'])
    out.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n');print(json.dumps(dict(radius_mm=radius,confirmation=d,image_coverage=cohorts['confirmation']['image_coverage'],passed=passed),indent=2))
if __name__=='__main__':run()
