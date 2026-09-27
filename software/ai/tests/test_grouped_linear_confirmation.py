import hashlib,json,sys
from pathlib import Path
import numpy as np
AI=Path(__file__).resolve().parents[1];ROOT=AI.parents[1];sys.path.insert(0,str(AI))
from vision.evaluate_grouped_linear_confirmation import checks_for
from evidence_artifacts import verify_frozen_artifacts


def test_acceptance_requires_every_condition_and_strict_occlusion_gain():
    base={c:dict(mean_mm=1.,tail=2,yaw_p95=1.) for c in ['standard','appearance_shift','partial','full']}
    assert not checks_for(base,base)[1]
    candidate={c:dict(v) for c,v in base.items()};candidate['full']['tail']=1
    assert checks_for(base,candidate)[1]
    candidate['standard']['mean_mm']=1.01
    assert not checks_for(base,candidate)[1]


def test_fresh_population_lineage_and_full_recount():
    p=AI/'eval/grouped_linear_confirmation_v1_plan.json';plan=json.loads(p.read_text());verify_frozen_artifacts(ROOT,plan['file_sha256'])
    r=json.loads((AI/'eval/grouped_linear_confirmation_v1_report.json').read_text());assert r['plan_sha256']==hashlib.sha256(p.read_bytes()).hexdigest()
    assert r['artifact_sha256']==plan['file_sha256'][plan['artifact']]
    rows=r['rows'];assert len(rows)==4000
    assert {(v['seed'],v['condition']) for v in rows}=={(s,c) for s in range(30001000,30002000) for c in plan['conditions']}
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


def test_selected_refit_lineage_and_export_parity_record():
    p=AI/'train/grouped_linear_refit_v1_plan.json';plan=json.loads(p.read_text());verify_frozen_artifacts(ROOT,plan['file_sha256'])
    r=json.loads((AI/'eval/grouped_linear_refit_v1_report.json').read_text());selection=json.loads((AI/'eval/grouped_linear_v1_report.json').read_text())
    assert r['plan_sha256']==hashlib.sha256(p.read_bytes()).hexdigest()
    assert r['alpha']==r['fit']['alpha']==selection['selected_alpha']==1.
    assert r['training_images']==2400 and r['training_groups']==600
    assert r['pixels_sha256']==selection['pixel_sha256']['rectangle']
    assert r['max_normalized_delta']<=plan['tolerance_normalized'] and r['roundtrip_exact'] and r['image_preprocess_exact']
    assert r['new_fits']==1 and r['hardware_writes']==r['physical_movements']==0
    verify_frozen_artifacts(ROOT,{r['artifact']:r['artifact_sha256']})
    confirmation=json.loads((AI/'eval/grouped_linear_confirmation_v1_report.json').read_text())
    assert confirmation['artifact_sha256']==r['artifact_sha256'] and confirmation['passed']


def test_local_export_retains_exact_final_coefficients():
    import pytest,torch
    from vision.linear_residual_pose import LinearResidualPoseNet
    r=json.loads((AI/'eval/grouped_linear_refit_v1_report.json').read_text());path=ROOT/r['artifact']
    if not path.exists():pytest.skip('ignored local checkpoint unavailable')
    model=LinearResidualPoseNet.from_export(torch.load(path,map_location='cpu',weights_only=True))
    for key in ['mean','scale','weights','intercept']:
        assert torch.equal(getattr(model,key),torch.tensor(r['fit'][key],dtype=torch.float64))
