"""Fixed support equal weighting on retained predictions; no hardware authority."""
import hashlib,json,math,sys
from pathlib import Path
AI=Path(__file__).resolve().parents[1];ROOT=AI.parents[1];sys.path[:0]=[str(AI),str(AI.parent/'src')]
import numpy as np
from vision.visible_candidate_decoder import weighted_fit
from vision.landmark_occlusions import render_controlled
from vision.synthetic_keyboard import catalog_for_workspace,transform_target

def run():
    p=AI/'eval/equal_support_v0_plan.json';m=json.loads(p.read_text())
    for f,h in m['file_sha256'].items():assert hashlib.sha256((ROOT/f).read_bytes()).hexdigest()==h
    source=json.loads((AI/'eval/visible_candidate_v0_report.json').read_text());catalog=catalog_for_workspace(ROOT);rows=[]
    for old in source['rows']:
        row=dict(seed=old['seed'],condition=old['condition'],accepted=old['accepted'],arms=dict(old['arms']))
        pose=weighted_fit(old['candidate']['points'],[float(v>=.5) for v in old['visibility']])
        assert (pose is not None)==old['accepted']
        if pose is not None:
            _,label,_=render_controlled(old['seed'],catalog,old['condition'],'ellipse');truth=label['pose']
            errors=[math.dist(transform_target(t.center.x,t.center.y,pose[:2],pose[2]),transform_target(t.center.x,t.center.y,truth[:2],truth[2])) for t in catalog.keyboard_targets.values()]
            row['equal_pose']=pose;row['arms']['equal']=dict(mean_mm=float(np.mean(errors)),maximum_mm=max(errors),yaw_degrees=abs(math.degrees(math.atan2(math.sin(pose[2]-truth[2]),math.cos(pose[2]-truth[2])))))
        rows.append(row)
    summaries={};checks={}
    for c in m['conditions']:
        allrows=[r for r in rows if r['condition']==c];selected=[r for r in allrows if r['accepted']]
        summaries[c]=dict(total=len(allrows),accepted=len(selected),coverage=len(selected)/len(allrows))
        for arm in ('subpixel','visible','equal'):
            summaries[c][arm]=dict(mean_mm=float(np.mean([r['arms'][arm]['mean_mm'] for r in selected])),tail=sum(r['arms'][arm]['maximum_mm']>3 for r in selected),yaw_p95=float(np.percentile([r['arms'][arm]['yaw_degrees'] for r in selected],95)))
        checks[c]={}
        for reference in ('subpixel','visible'):
            a,b=summaries[c][reference],summaries[c]['equal']
            checks[c][reference]=dict(coverage=len(selected)>=.9*len(allrows),mean=b['mean_mm']<=a['mean_mm']+1e-12,tail=b['tail']<=a['tail'],yaw=b['yaw_p95']<=1.1*a['yaw_p95'])
    report=dict(plan_sha256=hashlib.sha256(p.read_bytes()).hexdigest(),rows=rows,summaries=summaries,checks=checks,passed=all(all(v.values()) for c in checks.values() for v in c.values()),hardware_writes=0,physical_movements=0,qualification_installed=False,limitations=['Reused retained development predictions, unchanged support threshold and abstention','Non-increase mean allows exact all-supported equivalence; no threshold tuning','Synthetic geometry only; no calibrated visibility or runtime admission'])
    out=AI/'eval/equal_support_v0_report.json'
    if out.exists():raise FileExistsError(out)
    out.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(dict(summaries=summaries,checks=checks,passed=report['passed']),indent=2))
if __name__=='__main__':run()
