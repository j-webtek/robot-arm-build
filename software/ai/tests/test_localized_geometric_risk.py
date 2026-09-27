import hashlib,json,sys
from pathlib import Path

import numpy as np

AI=Path(__file__).resolve().parents[1];ROOT=AI.parents[1];sys.path.insert(0,str(AI))
from evidence_artifacts import verify_frozen_artifacts
from vision.evaluate_localized_geometric_risk import corner_features,ranking


def test_corner_features_are_image_and_pose_derived():
    heatmaps=np.zeros((4,48,64),dtype=np.float32)
    for corner,(y,x) in enumerate(((20,20),(20,40),(30,40),(30,20))):heatmaps[corner,y,x]=2
    result=corner_features(np.zeros(3,dtype=np.float32),heatmaps,np.zeros(4,dtype=np.float32))
    assert len(result['corner_residuals_mm'])==len(result['visibility_probabilities'])==4
    assert result['visibility_probabilities']==[.5]*4
    assert result['corner_residual_max']>=0 and result['visibility_weighted_residual']>=result['corner_residual_max']


def test_report_recounts_fresh_ranking_and_selects_nothing():
    plan_path=AI/'eval/localized_geometric_risk_v1_plan.json';plan=json.loads(plan_path.read_text())
    verify_frozen_artifacts(ROOT,plan['file_sha256'])
    report=json.loads((AI/'eval/localized_geometric_risk_v1_report.json').read_text())
    assert report['plan_sha256']==hashlib.sha256(plan_path.read_bytes()).hexdigest()
    start,count=plan['development_group'];rows=report['rows']
    assert len(rows)==count*len(plan['styles'])*len(plan['conditions'])
    assert {(r['seed'],r['style'],r['condition']) for r in rows}=={
        (s,t,c) for s in range(start,start+count) for t in plan['styles'] for c in plan['conditions']}
    for name in plan['score_names']:
        assert report['rankings'][name]==ranking(rows,name,plan['conditions'],plan['tolerance_mm'])
    baseline=report['rankings']['ensemble_disagreement'];passing=[]
    for name in plan['localized_score_names']:
        value=report['rankings'][name]
        expected={
            'minimum_scene_auc':value['scene_auc']>=plan['minimum_scene_auc'],
            'scene_auc_improvement':value['scene_auc']>=baseline['scene_auc']+plan['minimum_scene_auc_improvement'],
            'lowest_25_reduction':value['lowest_25_failure_rate']<=baseline['lowest_25_failure_rate']*plan['maximum_low_25_ratio'],
            'lowest_50_reduction':value['lowest_50_failure_rate']<=baseline['lowest_50_failure_rate']*plan['maximum_low_50_ratio'],
            'partial_auc':value['condition_image_auc']['partial']>=plan['minimum_obstructed_image_auc'],
            'full_auc':value['condition_image_auc']['full']>=plan['minimum_obstructed_image_auc']}
        assert report['checks'][name]==expected
        if all(expected.values()):passing.append(name)
    assert passing==[] and report['selected_feature'] is None and not report['passed_selection']
    assert report['new_model_fits']==report['calibration_fits']==report['optimizer_updates']==0
    assert report['hardware_writes']==report['physical_movements']==0 and not report['qualification_installed']
