"""Persistent synthetic failures, not independent repeated observations."""
import hashlib,json
from pathlib import Path
AI=Path(__file__).resolve().parents[1];ROOT=AI.parents[1]


def analyze(reports):
    indexed=[{a:{(v['seed'],v['condition']):v for v in r['results'][a]['rows']} for a in ['baseline','control','occlusion']} for r in reports]
    keys=set(indexed[0]['baseline'])
    assert all(set(rows)==keys for r in indexed for rows in r.values())
    rows=[]
    for key in sorted(keys):
        base=indexed[0]['baseline'][key]
        assert all(r['baseline'][key]==base for r in indexed)
        predictions=[r[a][key] for r in indexed for a in ['control','occlusion']]
        failures=[p['maximum_mm']>3 for p in predictions]
        rows.append(dict(seed=key[0],condition=key[1],baseline_bad=base['maximum_mm']>3,trained_failure_count=sum(failures),
            control_failure_count=sum(r['control'][key]['maximum_mm']>3 for r in indexed),candidate_failure_count=sum(r['occlusion'][key]['maximum_mm']>3 for r in indexed),
            translation_mean_mm=sum(p['translation_mm'] for p in predictions)/6,rotation_mean_mm=sum(p['rotation_only_maximum_mm'] for p in predictions)/6,
            translation_larger_count=sum(p['translation_mm']>=p['rotation_only_maximum_mm'] for p in predictions)))
    summaries={}
    for c in sorted({k[1] for k in keys}):
        cases=[r for r in rows if r['condition']==c];persistent=[r for r in cases if r['trained_failure_count']==6]
        summaries[c]=dict(cases=len(cases),failure_count_histogram={str(n):sum(r['trained_failure_count']==n for r in cases) for n in range(7)},
            persistent_seeds=[r['seed'] for r in persistent],persistent_shared_with_baseline=sum(r['baseline_bad'] for r in persistent),
            persistent_new=sum(not r['baseline_bad'] for r in persistent),baseline_recovered_all=sum(r['baseline_bad'] and r['trained_failure_count']==0 for r in cases),
            persistent_translation_majority=sum(r['translation_larger_count']>=4 for r in persistent))
    return rows,summaries


def run():
    p=AI/'eval/persistent_pose_v0_plan.json';plan=json.loads(p.read_text())
    for f,h in plan['file_sha256'].items():assert hashlib.sha256((ROOT/f).read_bytes()).hexdigest()==h
    rows,summaries=analyze([json.loads((ROOT/f).read_text()) for f in plan['inputs']])
    result=dict(plan_sha256=hashlib.sha256(p.read_bytes()).hexdigest(),rows=rows,summaries=summaries,hardware_writes=0,physical_movements=0,qualification_installed=False,limitations=['Same800 synthetic cases reused; six predictions are not six independent datasets','Persistence and translation/rotation magnitude diagnose errors,not causal simulator defects','No observation confidence,offset correction or runtime exclusion derived'])
    out=AI/'eval/persistent_pose_v0_report.json'
    if out.exists():raise FileExistsError(out)
    out.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(summaries,indent=2))
if __name__=='__main__':run()
