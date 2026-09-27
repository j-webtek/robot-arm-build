import hashlib,json,sys
from pathlib import Path
import torch

AI=Path(__file__).resolve().parents[1];ROOT=AI.parents[1];sys.path.insert(0,str(AI))
from evidence_artifacts import verify_frozen_artifacts
from train.train_obstruction_risk_scale import checks,passed
from vision.multiscale_obstruction_model import MultiScaleObstructionNet


def test_model_is_compact_multiscale_and_strict():
    model=MultiScaleObstructionNet()
    assert sum(p.numel() for p in model.parameters())==34381
    assert model(torch.zeros((2,3,96,128),dtype=torch.float32)).shape==(2,)
    for bad in (torch.zeros((2,3,95,128),dtype=torch.float32),torch.zeros((2,3,96,128),dtype=torch.float64)):
        try:model(bad);assert False
        except ValueError:pass


def test_report_lineage_population_and_failed_combined_rule():
    path=AI/'train/multiscale_obstruction_scale_v1_plan.json';plan=json.loads(path.read_text())
    verify_frozen_artifacts(ROOT,plan['file_sha256'])
    report=json.loads((AI/'eval/multiscale_obstruction_scale_v1_report.json').read_text())
    assert report['plan_sha256']==hashlib.sha256(path.read_bytes()).hexdigest()
    assert report['prior_report_sha256']==plan['file_sha256'][plan['prior_report']]
    assert report['model_parameters']==34381 and len(report['history'])==24 and report['optimizer_updates']==3000
    for name,(start,count) in plan['groups'].items():
        if name=='training':continue
        rows=report['cohorts'][name]['rows']
        assert len(rows)==count*len(plan['styles'])*len(plan['conditions'])
        assert {(r['seed'],r['style'],r['condition']) for r in rows}=={
            (s,t,c) for s in range(start,start+count) for t in plan['styles'] for c in plan['conditions']}
        assert all(r['scale_mm']>=max(r['disagreement_mm'],plan['scale_floor_mm']) for r in rows)
    expected=checks(report['selection_summary'],report['selection_conditions'],report['classifier'],plan)
    assert report['checks']==expected and report['passed_selection']==passed(expected)
    assert all(report['checks'][name] for name in ('classifier_auc','classifier_obstruction_recall','classifier_clean_false_positive'))
    assert not report['passed_selection']
    assert report['classifier_fits']==report['calibration_fits']==1
    assert report['hardware_writes']==report['physical_movements']==0 and not report['qualification_installed']
