import hashlib,json,sys
from pathlib import Path
import pytest
import torch
AI=Path(__file__).resolve().parents[1];ROOT=AI.parents[1];sys.path.insert(0,str(AI))
from evidence_artifacts import verify_frozen_artifacts
from vision.mask_conditioned_leaky_pose import LeakyMaskConditionedPoseNet
from vision.summarize_pose_mask_residual import summarize


def test_frozen_pairs_and_acceptance_recount():
    reports=[]
    for seed in (260926,260927,260928):
        p=AI/f'train/pose_leaky_residual_{seed}_plan.json';plan=json.loads(p.read_text());r=json.loads((AI/f'eval/pose_leaky_residual_{seed}_report.json').read_text());reports.append(r)
        verify_frozen_artifacts(ROOT,plan['file_sha256']);assert r['plan_sha256']==hashlib.sha256(p.read_bytes()).hexdigest()
        a,b=[r['results'][arm] for arm in ['control','occlusion']]
        for field in ['initial_state_sha256','frozen_state_sha256','training_pixels_sha256','teacher_predictions_sha256']:assert a[field]==b[field]
        assert plan['epochs']==8 and plan['learning_rate']==.001
        old_plan=json.loads((AI/f'train/pose_mask_residual_{seed}_plan.json').read_text())
        for field in ['epochs','learning_rate','anchor_coefficient','training_groups','development_groups','selection','rule']:assert plan[field]==old_plan[field]
        old_report=json.loads((AI/f'eval/pose_mask_residual_{seed}_report.json').read_text())
        assert a['initial_state_sha256']==old_report['results']['control']['initial_state_sha256']
        for arm in ['control','occlusion']:
            v=r['results'][arm];assert v['initial_pose_delta']==0 and v['frozen_state_unchanged']
            assert all(split['all_hidden_zero_images']==0 for split in v['variation'].values())
            assert all(all(std>0 for std in split['correction_std_normalized']) for split in v['variation'].values())
            assert v['training_images']==2400 and v['optimizer_updates']==304 and v['image_presentations']==19200
            assert v['selected_epoch']==min(v['history'],key=lambda e:e['development_mse'])['epoch']
            verify_frozen_artifacts(ROOT,{f'software/ai/results/pose_leaky_residual_{seed}_{arm}/model.pt':v['checkpoint_sha256']})
        for ref in ['baseline','control']:
            for condition in plan['conditions']:
                a=r['results'][ref]['summaries'][condition];b=r['results']['occlusion']['summaries'][condition]
                assert r['checks'][ref][condition]==dict(mean=b['mean_mm']<=a['mean_mm'],tail=b['tail']<=a['tail'],yaw=b['yaw_p95']<=1.1*a['yaw_p95'])
            assert r['checks'][ref]['occlusion_tail_improves']==(sum(r['results']['occlusion']['summaries'][c]['tail'] for c in ['partial','full'])<sum(r['results'][ref]['summaries'][c]['tail'] for c in ['partial','full']))
        assert r['passed']==all(all(all(v.values()) if isinstance(v,dict) else v for v in c.values()) for c in r['checks'].values())
        previous=json.loads((AI/f'eval/pose_warm_segmentation_{seed}_report.json').read_text())
        assert r['development_pixels_sha256']==previous['development_pixels_sha256']
    aggregate=json.loads((AI/'eval/pose_leaky_residual_v0_report.json').read_text())
    assert aggregate['summaries']==summarize(reports)
    for f,h in aggregate['source_sha256'].items():assert hashlib.sha256((AI/'eval'/f).read_bytes()).hexdigest()==h
    assert aggregate['full_passes']==[r['passed'] for r in reports]
    assert aggregate['hardware_writes']==aggregate['physical_movements']==0 and not aggregate['qualification_installed']


def test_local_exports_preserve_frozen_sources_and_change_residual():
    if not (AI/'results/pose_leaky_residual_260926_control/model.pt').exists():pytest.skip('ignored model checkpoints not available')
    for seed in (260926,260927,260928):
        pose=torch.load(AI/'results/translation_weighted_v0_translation_weighted/pose_model.pt',weights_only=True,map_location='cpu')
        head=torch.load(AI/f'results/segmentation_head_probe_{seed}/head.pt',weights_only=True,map_location='cpu')
        for arm,mode in [('control','constant'),('occlusion','predicted')]:
            artifact=torch.load(AI/f'results/pose_leaky_residual_{seed}_{arm}/model.pt',weights_only=True,map_location='cpu')
            model=LeakyMaskConditionedPoseNet.from_export(artifact);assert model.mode==mode
            assert all(torch.equal(v,model.backbone.state_dict()[k]) for k,v in pose.items())
            assert all(torch.equal(v,model.segmentation.state_dict()[k]) for k,v in head.items())
            assert bool(model.residual[-1].weight.count_nonzero())
