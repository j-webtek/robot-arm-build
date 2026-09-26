import hashlib,json,math,sys
from pathlib import Path
AI=Path(__file__).resolve().parents[1];ROOT=AI.parents[1];sys.path[:0]=[str(AI),str(AI.parent/'src')]
import numpy as np
from vision.landmark_occlusions import render_controlled
from vision.synthetic_keyboard import catalog_for_workspace

def run():
    p=AI/'eval/support_attribution_v0_plan.json';m=json.loads(p.read_text())
    for f,h in m['file_sha256'].items():assert hashlib.sha256((ROOT/f).read_bytes()).hexdigest()==h
    source=json.loads((AI/'eval/equal_support_v0_report.json').read_text());pred=json.loads((AI/'eval/visible_candidate_v0_report.json').read_text());catalog=catalog_for_workspace(ROOT);rows=[]
    for a,b in zip(source['rows'],pred['rows']):
        assert (a['seed'],a['condition'])==(b['seed'],b['condition'])
        _,label,_=render_controlled(a['seed'],catalog,a['condition'],'ellipse');truth=label['pose']
        fractions=[v['unoccluded_fraction'] for v in label['landmarks']];excluded=[i for i,v in enumerate(b['visibility']) if v<.5]
        clear=[i for i in excluded if fractions[i]==1];occluded=[i for i in excluded if fractions[i]<1]
        group='none' if not excluded else 'mixed' if clear and occluded else 'clear_only' if clear else 'occluded_only'
        row=dict(seed=a['seed'],condition=a['condition'],accepted=a['accepted'],group=group,excluded=excluded,geometric_visibility=fractions,clear_exclusions=len(clear),occluded_exclusions=len(occluded))
        if a['accepted']:
            old=b['candidate']['pose'];new=a['equal_pose']
            row.update(mean_delta_mm=a['arms']['equal']['mean_mm']-a['arms']['subpixel']['mean_mm'],
                translation_delta_mm=math.dist(new[:2],truth[:2])-math.dist(old[:2],truth[:2]),
                yaw_delta_degrees=a['arms']['equal']['yaw_degrees']-a['arms']['subpixel']['yaw_degrees'],
                new_tail=a['arms']['equal']['maximum_mm']>3 and a['arms']['subpixel']['maximum_mm']<=3,
                recovered_tail=a['arms']['equal']['maximum_mm']<=3 and a['arms']['subpixel']['maximum_mm']>3)
        rows.append(row)
    summary={}
    for group in ('none','clear_only','occluded_only','mixed'):
        allrows=[r for r in rows if r['group']==group];accepted=[r for r in allrows if r['accepted']]
        summary[group]=dict(cases=len(allrows),accepted=len(accepted),abstained=len(allrows)-len(accepted),clear_exclusions=sum(r['clear_exclusions'] for r in allrows),occluded_exclusions=sum(r['occluded_exclusions'] for r in allrows),new_tails=sum(r['new_tail'] for r in accepted),recovered_tails=sum(r['recovered_tail'] for r in accepted))
        for field in ('mean_delta_mm','translation_delta_mm','yaw_delta_degrees'):summary[group][field]=float(np.mean([r[field] for r in accepted])) if accepted else None
    report=dict(plan_sha256=hashlib.sha256(p.read_bytes()).hexdigest(),rows=rows,summary=summary,hardware_writes=0,physical_movements=0,qualification_installed=False,limitations=['Geometric synthetic visibility is diagnostic only, not perceptual or calibrated confidence','Reused development, associations not causal proof; no oracle fitting','Excluded partially visible corners counted as occluded, not necessarily unusable'])
    out=AI/'eval/support_attribution_v0_report.json'
    if out.exists():raise FileExistsError(out)
    out.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(summary,indent=2))
if __name__=='__main__':run()
