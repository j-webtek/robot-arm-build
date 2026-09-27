import hashlib,json,sys
from pathlib import Path

import torch

AI=Path(__file__).resolve().parents[1];ROOT=AI.parents[1];sys.path.insert(0,str(AI))
from evidence_artifacts import verify_frozen_artifacts
from vision.evaluate_localized_geometric_risk import ranking
from vision.pose_error_head import PoseErrorHead


def test_head_is_compact_normalized_and_strict():
    model=PoseErrorHead()
    assert sum(p.numel() for p in model.parameters())==52481
    assert model(torch.zeros((2,513),dtype=torch.float32)).shape==(2,)
    for bad in (torch.zeros((2,512),dtype=torch.float32),torch.zeros((2,513),dtype=torch.float64)):
        try:model(bad);assert False
        except ValueError:pass


def test_report_recounts_selection_and_preserves_near_miss():
    plan_path=AI/'train/pose_error_head_v1_plan.json';plan=json.loads(plan_path.read_text())
    verify_frozen_artifacts(ROOT,plan['file_sha256'])
    report=json.loads((AI/'eval/pose_error_head_v1_report.json').read_text())
    assert report['plan_sha256']==hashlib.sha256(plan_path.read_bytes()).hexdigest()
    assert report['model_parameters']==52481 and len(report['history'])==20 and report['optimizer_updates']==2500
    for name,(start,count) in plan['groups'].items():
        rows=report['training_rows'] if name=='training' else report['selection_rows']
        assert len(rows)==count*len(plan['styles'])*len(plan['conditions'])
        assert {(r['seed'],r['style'],r['condition']) for r in rows}=={
            (s,t,c) for s in range(start,start+count) for t in plan['styles'] for c in plan['conditions']}
    rows=report['selection_rows']
    for name in ('ensemble_disagreement','pose_error_head'):
        assert report['rankings'][name]==ranking(rows,name,plan['conditions'],plan['tolerance_mm'])
    baseline=report['rankings']['ensemble_disagreement'];candidate=report['rankings']['pose_error_head']
    expected={
        'minimum_scene_auc':candidate['scene_auc']>=plan['minimum_scene_auc'],
        'scene_auc_improvement':candidate['scene_auc']>=baseline['scene_auc']+plan['minimum_scene_auc_improvement'],
        'lowest_25_reduction':candidate['lowest_25_failure_rate']<=baseline['lowest_25_failure_rate']*plan['maximum_low_25_ratio'],
        'lowest_50_reduction':candidate['lowest_50_failure_rate']<=baseline['lowest_50_failure_rate']*plan['maximum_low_50_ratio'],
        'condition_image_auc':{c:v>=plan['minimum_condition_image_auc'] for c,v in candidate['condition_image_auc'].items()}}
    assert report['checks']==expected and not expected['lowest_25_reduction']
    assert all(v for k,v in expected.items() if isinstance(v,bool) and k!='lowest_25_reduction')
    assert all(expected['condition_image_auc'].values()) and not report['passed_selection']
    assert report['model_fits']==1 and report['calibration_fits']==0
    assert report['hardware_writes']==report['physical_movements']==0 and not report['qualification_installed']
