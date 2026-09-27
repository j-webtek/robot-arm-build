import copy,hashlib,json,sys
from pathlib import Path
import numpy as np
import pytest
from PIL import Image
AI=Path(__file__).resolve().parents[1];ROOT=AI.parents[1];sys.path.insert(0,str(AI))
from vision.image_scale_export import validate,predict_image
from vision.evaluate_scaled_uncertainty import summarize
from vision.evaluate_grouped_uncertainty import calibrate
from evidence_artifacts import verify_frozen_artifacts


def test_export_rejects_malformed_and_preserves_image_output():
    a=json.loads((AI/'eval/image_scale_refit_v1_model.json').read_text());validate(a)
    image=Image.new('RGB',(128,96),(100,120,140))
    assert predict_image(a,image)==predict_image(json.loads(json.dumps(a)),image)
    for mutate in [lambda b:b.update(extra=1),lambda b:b.update(pose_sha256='bad'),lambda b:b['fit'].update(scale=[0]*56),lambda b:b['fit'].update(weights=[float('nan')]*56)]:
        b=copy.deepcopy(a);mutate(b)
        with pytest.raises(ValueError):validate(b)


def test_accepted_subset_counts_do_not_hide_errors():
    rows=[dict(seed=1,scale_mm=1.,error_mm=4.),dict(seed=1,scale_mm=4.,error_mm=5.),dict(seed=2,scale_mm=1.,error_mm=1.)]
    s=summarize(rows,2.,3.)
    assert s['accepted_images']==2 and s['accepted_errors_over_3']==1 and s['accepted_bound_violations']==1
    assert s['covered_scenes']==1 and s['scenes_with_acceptance']==2 and s['accepted_scenes_with_bound_violation']==1
    empty=summarize(rows,10.,3.)
    assert empty['accepted_images']==0 and empty['accepted_scene_violation_wilson95'] is None


def test_export_lineage_and_parity_evidence():
    p=AI/'train/image_scale_refit_v1_plan.json';plan=json.loads(p.read_text());verify_frozen_artifacts(ROOT,plan['file_sha256'])
    r=json.loads((AI/'eval/image_scale_refit_v1_report.json').read_text());assert r['plan_sha256']==hashlib.sha256(p.read_bytes()).hexdigest()
    assert hashlib.sha256((ROOT/r['artifact']).read_bytes()).hexdigest()==r['artifact_sha256']
    assert r['images']==4800 and r['roundtrip_exact'] and r['image_max_delta_mm']<=1e-12
    assert r['scale_fits']==1 and r['pose_fits']==r['calibration_fits']==0


def test_calibration_confirmation_populations_and_recount():
    p=AI/'eval/scaled_uncertainty_v1_plan.json';plan=json.loads(p.read_text());verify_frozen_artifacts(ROOT,plan['file_sha256'])
    r=json.loads((AI/'eval/scaled_uncertainty_v1_report.json').read_text());assert r['plan_sha256']==hashlib.sha256(p.read_bytes()).hexdigest()
    sets=[]
    for name,cohort in r['cohorts'].items():
        start,count=plan['groups'][name];seeds=set(range(start,start+count));sets.append(seeds)
        assert len(cohort['rows'])==4000 and {(v['seed'],v['condition']) for v in cohort['rows']}=={(s,c) for s in seeds for c in plan['conditions']}
        scores=[dict(seed=s,normalized_max=max(v['error_mm']/v['scale_mm'] for v in cohort['rows'] if v['seed']==s)) for s in sorted(seeds)]
        assert cohort['scene_scores']==scores
    assert not sets[0]&sets[1]
    rank,q=calibrate([v['normalized_max'] for v in r['cohorts']['calibration']['scene_scores']],.01)
    assert (rank,q)==(r['rank'],r['normalized_quantile'])
    c=r['cohorts']['confirmation'];s=summarize(c['rows'],q,3.);assert c['summary']==s
    for condition in plan['conditions']:assert c['conditions'][condition]==summarize([v for v in c['rows'] if v['condition']==condition],q,3.)
    assert r['passed']==(s['scene_coverage']>=.99 and s['accepted_fraction']>0)
    assert r['calibration_fits']==1 and r['scale_fits']==r['pose_fits']==r['hardware_writes']==r['physical_movements']==0
    assert not r['qualification_installed']
