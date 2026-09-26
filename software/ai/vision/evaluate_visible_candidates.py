import hashlib,json,math,sys
from pathlib import Path
AI=Path(__file__).resolve().parents[1];ROOT=AI.parents[1];sys.path[:0]=[str(AI),str(AI.parent/'src')]
import numpy as np
import torch
from vision.temperature_visibility_model import TemperatureVisibilityNet
from vision.landmark_model import heatmap_coordinates
from vision.landmark_occlusions import render_controlled
from vision.synthetic_keyboard import catalog_for_workspace,transform_target
from vision.evaluate_dark_only_normalization import normalize
from vision.visible_candidate_decoder import refine,weighted_fit
from train.train_landmarks import pose_from_corners

def run():
    p=AI/'eval/visible_candidate_v0_plan.json';m=json.loads(p.read_text())
    for f,h in m['file_sha256'].items():assert hashlib.sha256((ROOT/f).read_bytes()).hexdigest()==h
    ck=ROOT/m['checkpoint'];assert hashlib.sha256(ck.read_bytes()).hexdigest()==m['checkpoint_sha256']
    torch.set_num_threads(4);model=TemperatureVisibilityNet('t05');model.load_state_dict(torch.load(ck,weights_only=True,map_location='cpu'));model.eval()
    catalog=catalog_for_workspace(ROOT);rows=[]
    for seed in range(15000000,15000200):
        for condition in m['conditions']:
            image,label,_=render_controlled(seed,catalog,condition,'ellipse');image,_=normalize(image)
            with torch.no_grad():out=model(torch.from_numpy(np.asarray(image).transpose(2,0,1).copy())[None].float()/255)
            candidate=refine(out['heatmap_logits'][0].flatten(1).softmax(-1).reshape(4,48,64).numpy())
            visibility=out['visibility_logits'][0].sigmoid().numpy()
            weighted=weighted_fit(candidate['points'],visibility)
            poses={'subpixel':candidate['pose']}
            if weighted is not None:poses['visible']=weighted
            truth=label['pose'];row=dict(seed=seed,condition=condition,candidate=candidate,visibility=visibility.tolist(),accepted=weighted is not None,arms={})
            for name,pose in poses.items():
                errors=[math.dist(transform_target(t.center.x,t.center.y,pose[:2],pose[2]),transform_target(t.center.x,t.center.y,truth[:2],truth[2])) for t in catalog.keyboard_targets.values()]
                row['arms'][name]=dict(mean_mm=float(np.mean(errors)),maximum_mm=max(errors),yaw_degrees=abs(math.degrees(math.atan2(math.sin(pose[2]-truth[2]),math.cos(pose[2]-truth[2])))))
            rows.append(row)
    summaries={};checks={}
    for c in m['conditions']:
        all_rows=[r for r in rows if r['condition']==c];selected=[r for r in all_rows if r['accepted']]
        summaries[c]=dict(total=len(all_rows),accepted=len(selected),coverage=len(selected)/len(all_rows))
        for arm in ('subpixel','visible'):
            summaries[c][arm]=dict(mean_mm=float(np.mean([r['arms'][arm]['mean_mm'] for r in selected])) if selected else None,tail=sum(r['arms'][arm]['maximum_mm']>3 for r in selected),yaw_p95=float(np.percentile([r['arms'][arm]['yaw_degrees'] for r in selected],95)) if selected else None)
        a,b=summaries[c]['subpixel'],summaries[c]['visible']
        checks[c]=dict(coverage=len(selected)>=len(all_rows)*.9,mean=bool(selected) and b['mean_mm']<a['mean_mm'],tail=b['tail']<=a['tail'],yaw=bool(selected) and b['yaw_p95']<=a['yaw_p95']*1.1)
    report=dict(plan_sha256=hashlib.sha256(p.read_bytes()).hexdigest(),rows=rows,summaries=summaries,checks=checks,passed=all(all(v.values()) for v in checks.values()),hardware_writes=0,physical_movements=0,qualification_installed=False,limitations=['Reused synthetic development; visibility is uncalibrated','Same accepted subset for paired comparison; abstained cases retained','Fixed0.5 support threshold,minimum3 corners,probability weights; no tuning','Candidate combination selection still includes all corners; no measured calibration or execution authority'])
    path=AI/'eval/visible_candidate_v0_report.json'
    if path.exists():raise FileExistsError(path)
    path.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(dict(summaries=summaries,checks=checks,passed=report['passed']),indent=2))
if __name__=='__main__':run()
