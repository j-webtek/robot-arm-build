"""Retained paired residual attribution; development diagnostics only."""
import hashlib,json
from pathlib import Path
import numpy as np
AI=Path(__file__).resolve().parents[1];ROOT=AI.parents[1]


def compare(a,b):
    assert a.keys()==b.keys()
    rows=[]
    for seed in sorted(a):
        x,y=a[seed],b[seed]
        rows.append(dict(seed=seed,mean_change_mm=y['mean_mm']-x['mean_mm'],translation_change_mm=y['translation_mm']-x['translation_mm'],rotation_change_mm=y['rotation_only_maximum_mm']-x['rotation_only_maximum_mm'],
            signed_translation_change_mm=[v-u for u,v in zip(x['translation_delta_mm'],y['translation_delta_mm'])]))
    delta=np.array([r['mean_change_mm'] for r in rows]);positive=np.maximum(delta,0);rank=np.argsort(-positive);top=rank[:10]
    return dict(rows=rows,summary=dict(mean_change_mm=float(delta.mean()),median_change_mm=float(np.median(delta)),worsened=int((delta>0).sum()),improved=int((delta<0).sum()),
        translation_mean_change_mm=float(np.mean([r['translation_change_mm'] for r in rows])),rotation_mean_change_mm=float(np.mean([r['rotation_change_mm'] for r in rows])),
        signed_translation_mean_change_mm=np.mean([r['signed_translation_change_mm'] for r in rows],axis=0).tolist(),
        top10_positive_share=float(positive[top].sum()/positive.sum()) if positive.sum() else 0.,
        mean_change_excluding_top10_mm=float(np.delete(delta,top).mean()),top10_seeds=[rows[i]['seed'] for i in top]))


def run():
    p=AI/'eval/appearance_residual_v0_plan.json';plan=json.loads(p.read_text())
    for f,h in plan['file_sha256'].items():assert hashlib.sha256((ROOT/f).read_bytes()).hexdigest()==h
    source=json.loads((ROOT/plan['input']).read_text());indexed={a:{c:{r['seed']:r for r in result['rows'] if r['condition']==c} for c in ['standard','appearance_shift']} for a,result in source['results'].items()}
    comparisons={a+'_appearance_vs_standard':compare(cs['standard'],cs['appearance_shift']) for a,cs in indexed.items()}
    for c in ['standard','appearance_shift']:
        comparisons['candidate_vs_baseline_'+c]=compare(indexed['baseline'][c],indexed['occlusion'][c])
        comparisons['candidate_vs_control_'+c]=compare(indexed['control'][c],indexed['occlusion'][c])
    report=dict(plan_sha256=hashlib.sha256(p.read_bytes()).hexdigest(),comparisons=comparisons,hardware_writes=0,physical_movements=0,qualification_installed=False,limitations=['Reused synthetic development,200 paired seeds','Top10 trimming is descriptive concentration analysis,never exclusion from acceptance scoring','Unsigned rotation magnitude and signed translation changes do not prove causal bias or supply correction offsets'])
    out=AI/'eval/appearance_residual_v0_report.json'
    if out.exists():raise FileExistsError(out)
    out.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:v['summary'] for k,v in comparisons.items()},indent=2))
if __name__=='__main__':run()
