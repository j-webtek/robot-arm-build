import hashlib,json,sys
from pathlib import Path

import pytest

AI=Path(__file__).resolve().parents[1];ROOT=AI.parents[1];sys.path.insert(0,str(AI))
from evidence_artifacts import verify_frozen_artifacts
from train.select_ensemble_scale_mapping import evaluate_checks,checks_pass
from train.select_multiscale_obstruction_mapping import scaled_rows
from vision.evaluate_ensemble_scaled_uncertainty import summarize
from vision.evaluate_grouped_uncertainty import calibrate


def test_low_gain_mapping_uses_only_probability_and_disagreement():
    rows=[{"disagreement_mm":.5,"obstruction_probability":0.,"error_mm":1.},
          {"disagreement_mm":2.,"obstruction_probability":1.,"error_mm":1.}]
    mapped=scaled_rows(rows,.125,1.)
    assert [r['scale_mm'] for r in mapped]==pytest.approx([1.,2.25])
    assert [r['error_mm'] for r in mapped]==[1.,1.]


def test_report_recounts_every_mapping_and_selects_nothing():
    plan_path=AI/'train/multiscale_obstruction_mapping_v1_plan.json';plan=json.loads(plan_path.read_text())
    verify_frozen_artifacts(ROOT,plan['file_sha256'])
    report=json.loads((AI/'eval/multiscale_obstruction_mapping_v1_report.json').read_text())
    assert report['plan_sha256']==hashlib.sha256(plan_path.read_bytes()).hexdigest()
    assert report['prior_report_sha256']==plan['file_sha256'][plan['prior_report']]
    assert report['classifier_checkpoint_sha256']==plan['file_sha256'][plan['classifier_checkpoint']]
    for name,(start,count) in plan['groups'].items():
        rows=report['cohorts'][name]['rows']
        assert len(rows)==count*len(plan['styles'])*len(plan['conditions'])
        assert {(r['seed'],r['style'],r['condition']) for r in rows}=={
            (s,t,c) for s in range(start,start+count) for t in plan['styles'] for c in plan['conditions']}
    cal=report['cohorts']['mapping_calibration']['rows'];sel=report['cohorts']['selection']['rows']
    start,count=plan['groups']['mapping_calibration'];passing=[]
    for gain in plan['gains']:
        name=f'gain_{gain:g}';result=report['results'][name]
        mapped=scaled_rows(cal,gain,plan['scale_floor_mm'])
        scores=[{'seed':s,'normalized_max':max(r['error_mm']/r['scale_mm'] for r in mapped if r['seed']==s)} for s in range(start,start+count)]
        rank,q=calibrate([r['normalized_max'] for r in scores],plan['alpha'])
        chosen=scaled_rows(sel,gain,plan['scale_floor_mm']);summary=summarize(chosen,q,plan['tolerance_mm'])
        conditions={c:summarize([r for r in chosen if r['condition']==c],q,plan['tolerance_mm']) for c in plan['conditions']}
        decision=evaluate_checks(summary,conditions,plan)
        assert result['mapping_calibration_scene_scores']==scores and result['rank']==rank==991
        assert result['normalized_quantile']==pytest.approx(q)
        assert result['selection_summary']==summary and result['selection_conditions']==conditions
        assert result['checks']==decision and result['passed']==checks_pass(decision)
        if result['passed']:passing.append(name)
    assert passing==[] and report['selected_mapping'] is None and not report['passed_selection']
    assert report['calibration_fits']==4 and report['new_model_fits']==report['optimizer_updates']==0
    assert report['hardware_writes']==report['physical_movements']==0 and not report['qualification_installed']
