"""Single preregistered untouched synthetic evaluation of frozen export."""
import hashlib,json,sys
from pathlib import Path
AI=Path(__file__).resolve().parents[1];ROOT=AI.parents[1];sys.path[:0]=[str(AI),str(AI.parent/'src')]
import numpy as np
import torch
from vision.linear_residual_pose import LinearResidualPoseNet
from vision.pose_model import KeyboardPoseNet
from vision.landmark_occlusions import render_controlled
from vision.synthetic_keyboard import catalog_for_workspace
from vision.evaluate_dark_only_normalization import normalize
from vision.train_pose import _pose_from_prediction
from vision.diagnose_pose_tail import decompose


def checks_for(baseline,candidate):
    checks={c:dict(mean=candidate[c]['mean_mm']<=baseline[c]['mean_mm'],tail=candidate[c]['tail']<=baseline[c]['tail'],yaw=candidate[c]['yaw_p95']<=1.1*baseline[c]['yaw_p95']) for c in baseline}
    checks['occlusion_tail_improves']=sum(candidate[c]['tail'] for c in ['partial','full'])<sum(baseline[c]['tail'] for c in ['partial','full'])
    return checks,all(all(v.values()) if isinstance(v,dict) else v for v in checks.values())


def run():
    p=AI/'eval/linear_fresh_v0_plan.json';plan=json.loads(p.read_text())
    for f,h in plan['file_sha256'].items():
        if hashlib.sha256((ROOT/f).read_bytes()).hexdigest()!=h:raise ValueError('frozen artifact mismatch: '+f)
    out=AI/'eval/linear_fresh_v0_report.json'
    if out.exists():raise FileExistsError(out)
    torch.set_num_threads(4);catalog=catalog_for_workspace(ROOT)
    candidate=LinearResidualPoseNet.from_export(torch.load(ROOT/plan['artifact'],map_location='cpu',weights_only=True))
    baseline=KeyboardPoseNet().eval();baseline.load_state_dict(torch.load(ROOT/plan['checkpoint'],map_location='cpu',weights_only=True))
    assert all(torch.equal(v,candidate.backbone.state_dict()[k]) for k,v in baseline.state_dict().items())
    pixels=[];meta=[]
    start,count=plan['groups']
    for seed in range(start,start+count):
        for c in plan['conditions']:
            image,label,_=render_controlled(seed,catalog,c,'ellipse');image,_=normalize(image)
            pixels.append(np.asarray(image.resize((128,96))).transpose(2,0,1).copy());meta.append((seed,c,label['pose']))
    pixels=np.stack(pixels);x=torch.from_numpy(pixels).float()/255;predictions={}
    with torch.no_grad():
        for name,model in [('baseline',baseline),('candidate',candidate)]:predictions[name]=torch.cat([model(batch) for batch in x.split(64)]).numpy()
    rows=[]
    for i,(seed,c,truth) in enumerate(meta):
        rows.append(dict(seed=seed,condition=c,arms={a:decompose(_pose_from_prediction(v[i]),truth,catalog.keyboard_targets.values()) for a,v in predictions.items()}))
    summary={}
    for arm in predictions:
        summary[arm]={}
        for c in plan['conditions']:
            selected=[r['arms'][arm] for r in rows if r['condition']==c]
            summary[arm][c]=dict(cases=len(selected),mean_mm=float(np.mean([v['mean_mm'] for v in selected])),tail=sum(v['maximum_mm']>3 for v in selected),yaw_p95=float(np.percentile([v['yaw_degrees'] for v in selected],95)))
    checks,passed=checks_for(summary['baseline'],summary['candidate'])
    transitions={c:dict(recovered=sum(r['arms']['baseline']['maximum_mm']>3 and r['arms']['candidate']['maximum_mm']<=3 for r in rows if r['condition']==c),introduced=sum(r['arms']['baseline']['maximum_mm']<=3 and r['arms']['candidate']['maximum_mm']>3 for r in rows if r['condition']==c)) for c in plan['conditions']}
    result=dict(plan_sha256=hashlib.sha256(p.read_bytes()).hexdigest(),artifact_sha256=plan['file_sha256'][plan['artifact']],pixels_sha256=hashlib.sha256(pixels.tobytes()).hexdigest(),prediction_sha256={a:hashlib.sha256(v.tobytes()).hexdigest() for a,v in predictions.items()},rows=rows,summaries=summary,transitions=transitions,checks=checks,passed=passed,
        new_fits=0,hardware_writes=0,physical_movements=0,qualification_installed=False,
        limitations=['One frozen evaluation on previously unused seeds from the same synthetic renderer; not physical-camera validation',
        'Candidate selected on reused development; no refit, normalization change or threshold selection in this evaluation',
        'Paired conditions share scene seeds and are not4000 independent physical trials',
        'This seed range is now consumed evaluation data; cannot be represented as untouched in later selection',
        'No calibrated observation uncertainty or motion authority follows from passing synthetic accuracy'])
    out.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n');print(json.dumps(dict(summaries=summary,transitions=transitions,checks=checks,passed=passed),indent=2))
if __name__=='__main__':run()
