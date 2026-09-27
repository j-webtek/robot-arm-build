import hashlib,json,sys
from pathlib import Path

AI=Path(__file__).resolve().parents[1];ROOT=AI.parents[1];sys.path.insert(0,str(AI))
from evidence_artifacts import verify_frozen_artifacts
from train.train_tail_risk_head import checks_pass,decision_checks
from vision.evaluate_localized_geometric_risk import ranking


def test_report_recounts_tail_selection_and_passes():
    plan_path=AI/'train/tail_risk_head_v1_plan.json';plan=json.loads(plan_path.read_text())
    verify_frozen_artifacts(ROOT,plan['file_sha256'])
    report=json.loads((AI/'eval/tail_risk_head_v1_report.json').read_text())
    assert report['plan_sha256']==hashlib.sha256(plan_path.read_bytes()).hexdigest()
    assert report['prior_report_sha256']==plan['file_sha256'][plan['prior_report']]
    assert report['model_parameters']==52481 and len(report['history'])==20 and report['optimizer_updates']==2500
    for name,(start,count) in plan['groups'].items():
        rows=report['training_rows'] if name=='training' else report['selection_rows']
        assert len(rows)==count*len(plan['styles'])*len(plan['conditions'])
        assert {(r['seed'],r['style'],r['condition']) for r in rows}=={
            (s,t,c) for s in range(start,start+count) for t in plan['styles'] for c in plan['conditions']}
    positives=sum(r['error_mm']>plan['tolerance_mm'] for r in report['training_rows'])
    assert positives==report['training_positive_images']==688
    assert len(report['training_rows'])-positives==report['training_negative_images']
    assert report['positive_weight']==report['training_negative_images']/positives
    rows=report['selection_rows']
    for name in ('ensemble_disagreement','tail_risk_head'):
        assert report['rankings'][name]==ranking(rows,name,plan['conditions'],plan['tolerance_mm'])
    expected=decision_checks(report['rankings']['tail_risk_head'],report['rankings']['ensemble_disagreement'],plan)
    assert report['checks']==expected and checks_pass(expected) and report['passed_selection']
    assert report['model_fits']==1 and report['calibration_fits']==0
    assert report['hardware_writes']==report['physical_movements']==0 and not report['qualification_installed']
