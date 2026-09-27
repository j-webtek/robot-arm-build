import hashlib,json,sys
from pathlib import Path
import torch
AI=Path(__file__).resolve().parents[1];ROOT=AI.parents[1];sys.path.insert(0,str(AI))
from evidence_artifacts import verify_frozen_artifacts
from train.train_obstruction_risk_scale import checks,passed
from vision.obstruction_risk_model import ObstructionRiskNet


def test_model_is_compact_and_strict():
    model=ObstructionRiskNet();assert sum(p.numel() for p in model.parameters())==69561
    assert model(torch.zeros((2,3,96,128),dtype=torch.float32)).shape==(2,)
    try:model(torch.zeros((2,3,95,128),dtype=torch.float32));assert False
    except ValueError:pass


def test_report_lineage_population_and_failed_rule():
    path=AI/'train/obstruction_risk_scale_v1_plan.json';plan=json.loads(path.read_text());verify_frozen_artifacts(ROOT,plan['file_sha256'])
    report=json.loads((AI/'eval/obstruction_risk_scale_v1_report.json').read_text());assert report['plan_sha256']==hashlib.sha256(path.read_bytes()).hexdigest()
    assert report['model_parameters']==69561 and len(report['history'])==16 and report['optimizer_updates']==2000
    for name,(start,count) in plan['groups'].items():
        if name=='training':continue
        rows=report['cohorts'][name]['rows'];assert len(rows)==count*8
        assert {(r['seed'],r['style'],r['condition']) for r in rows}=={(s,t,c) for s in range(start,start+count) for t in plan['styles'] for c in plan['conditions']}
        assert all(r['scale_mm']>=max(r['disagreement_mm'],1.0) for r in rows)
    expected=checks(report['selection_summary'],report['selection_conditions'],report['classifier'],plan)
    assert report['checks']==expected and report['passed_selection']==passed(expected)
    assert not report['passed_selection'];assert report['classifier_fits']==report['calibration_fits']==1
    assert report['hardware_writes']==report['physical_movements']==0 and not report['qualification_installed']
