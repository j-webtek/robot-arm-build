import hashlib,json,math,sys
from pathlib import Path
import pytest
AI=Path(__file__).resolve().parents[1];ROOT=AI.parents[1];sys.path.insert(0,str(AI))
from vision.evaluate_grouped_uncertainty import calibrate,decision,wilson
from evidence_artifacts import verify_frozen_artifacts


def test_quantile_rank_and_small_sample_abstention():
    assert calibrate(list(range(1000)),.01)==(991,990)
    rank,radius=calibrate([1.,2.],.01)
    assert rank==3 and radius is None
    assert not decision([1.,2.],radius,3.)['accepted']
    assert decision([3.,4.],3.,3.)['covered']==1
    assert decision([3.],3.,3.)['accepted']
    assert not decision([1.],3.00001,3.)['accepted']


@pytest.mark.parametrize('scores,alpha',[([],.01),([float('nan')],.01),([-1],.01),([1],0),([1],1)])
def test_invalid_calibration_rejected(scores,alpha):
    with pytest.raises(ValueError):calibrate(scores,alpha)


def test_wilson_interval_reference_and_extremes():
    low,high=wilson(50,100)
    assert low==pytest.approx(.4038315303659956) and high==pytest.approx(.5961684696340044)
    assert wilson(0,100)[0]==pytest.approx(0,abs=1e-15) and wilson(100,100)[1]==pytest.approx(1,abs=1e-15)


def test_report_grouping_independence_and_bound_recount():
    p=AI/'eval/grouped_uncertainty_v1_plan.json';plan=json.loads(p.read_text());verify_frozen_artifacts(ROOT,plan['file_sha256'])
    r=json.loads((AI/'eval/grouped_uncertainty_v1_report.json').read_text())
    assert r['plan_sha256']==hashlib.sha256(p.read_bytes()).hexdigest()
    assert r['artifact_sha256']==plan['file_sha256'][plan['artifact']]
    seed_sets=[]
    for name,cohort in r['cohorts'].items():
        start,count=plan['groups'][name];seeds=set(range(start,start+count));seed_sets.append(seeds)
        assert len(cohort['rows'])==4000
        assert {(v['seed'],v['condition']) for v in cohort['rows']}=={(s,c) for s in seeds for c in plan['conditions']}
        expected=[dict(seed=s,maximum_mm=max(v['maximum_mm'] for v in cohort['rows'] if v['seed']==s)) for s in sorted(seeds)]
        assert cohort['scenes']==expected
        assert cohort['maximum_error_mm']==max(v['maximum_mm'] for v in expected)
    assert not seed_sets[0]&seed_sets[1]
    rank,radius=calibrate([v['maximum_mm'] for v in r['cohorts']['calibration']['scenes']],plan['alpha'])
    assert (rank,radius)==(r['rank'],r['radius_mm'])
    confirmation=r['cohorts']['confirmation'];scores=[v['maximum_mm'] for v in confirmation['scenes']]
    d=decision(scores,radius,plan['tolerance_mm']);assert confirmation['scene_decision']==d
    assert confirmation['bound_violations']==[v for v in confirmation['scenes'] if v['maximum_mm']>radius]
    assert confirmation['image_coverage']==sum(v['maximum_mm']<=radius for v in confirmation['rows'])/4000
    assert r['passed']==(d['coverage']>=1-plan['alpha'] and d['accepted_fraction']>0)==False
    assert r['calibration_fits']==1 and r['new_model_fits']==r['hardware_writes']==r['physical_movements']==0
    assert not r['qualification_installed']
