import hashlib,json,sys
from pathlib import Path
import numpy as np
AI=Path(__file__).resolve().parents[1];ROOT=AI.parents[1];sys.path.insert(0,str(AI))
from vision.evaluate_linear_fresh import checks_for
from evidence_artifacts import verify_frozen_artifacts


def test_acceptance_requires_every_condition_and_strict_occlusion_gain():
    base={c:dict(mean_mm=1.,tail=2,yaw_p95=1.) for c in ['standard','appearance_shift','partial','full']}
    assert not checks_for(base,base)[1]
    candidate={c:dict(v) for c,v in base.items()};candidate['full']['tail']=1
    assert checks_for(base,candidate)[1]
    candidate['standard']['mean_mm']=1.01
    assert not checks_for(base,candidate)[1]


def test_fresh_population_lineage_and_full_recount():
    p=AI/'eval/linear_fresh_v0_plan.json';plan=json.loads(p.read_text());verify_frozen_artifacts(ROOT,plan['file_sha256'])
    r=json.loads((AI/'eval/linear_fresh_v0_report.json').read_text());assert r['plan_sha256']==hashlib.sha256(p.read_bytes()).hexdigest()
    assert r['artifact_sha256']==plan['file_sha256'][plan['artifact']]
    rows=r['rows'];assert len(rows)==4000
    assert {(v['seed'],v['condition']) for v in rows}=={(s,c) for s in range(30000000,30001000) for c in plan['conditions']}
    for arm in ['baseline','candidate']:
        for c in plan['conditions']:
            values=[v['arms'][arm] for v in rows if v['condition']==c];summary=r['summaries'][arm][c]
            assert summary==dict(cases=1000,mean_mm=float(np.mean([v['mean_mm'] for v in values])),tail=sum(v['maximum_mm']>3 for v in values),yaw_p95=float(np.percentile([v['yaw_degrees'] for v in values],95)))
    for c in plan['conditions']:
        group=[v for v in rows if v['condition']==c]
        expected=dict(recovered=sum(v['arms']['baseline']['maximum_mm']>3 and v['arms']['candidate']['maximum_mm']<=3 for v in group),introduced=sum(v['arms']['baseline']['maximum_mm']<=3 and v['arms']['candidate']['maximum_mm']>3 for v in group))
        assert r['transitions'][c]==expected
        assert r['summaries']['candidate'][c]['tail']==r['summaries']['baseline'][c]['tail']-expected['recovered']+expected['introduced']
    checks,passed=checks_for(r['summaries']['baseline'],r['summaries']['candidate']);assert checks==r['checks'] and passed==r['passed']
    assert r['new_fits']==r['hardware_writes']==r['physical_movements']==0 and not r['qualification_installed']
