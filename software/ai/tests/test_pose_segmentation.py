import hashlib,json,sys
from pathlib import Path
import torch
AI=Path(__file__).resolve().parents[1];ROOT=AI.parents[1];sys.path.insert(0,str(AI))
from evidence_artifacts import verify_frozen_artifacts
from train.segmentation_auxiliary import SegmentationPoseNet
from vision.summarize_pose_segmentation import summarize


def test_training_lineage_same_inputs_and_all_runs():
    reports=[]
    for seed in [260926,260927,260928]:
        p=AI/f'train/pose_segmentation_{seed}_plan.json';plan=json.loads(p.read_text());r=json.loads((AI/f'eval/pose_segmentation_{seed}_report.json').read_text());reports.append(r)
        assert r['plan_sha256']==hashlib.sha256(p.read_bytes()).hexdigest();verify_frozen_artifacts(ROOT,plan['file_sha256'])
        a,b=[r['results'][arm] for arm in ['control','occlusion']]
        for k in ['initial_state_sha256','training_pixels_sha256','training_mask_sha256','teacher_predictions_sha256']:assert a[k]==b[k]
        for arm in ['control','occlusion']:
            result=r['results'][arm];assert result['training_images']==2400 and len(result['history'])==4
            assert result['selected_epoch']==min(result['history'],key=lambda h:h['development_mse'])['epoch']
            directory=f'software/ai/results/pose_segmentation_{seed}_{arm}'
            verify_frozen_artifacts(ROOT,{directory+'/pose_model.pt':result['checkpoint_sha256'],directory+'/training_model.pt':result['training_model_sha256']})
        old=json.loads((AI/'eval/pose_anchor_v0_report.json').read_text());assert r['development_pixels_sha256']==old['development_pixels_sha256']
    aggregate=json.loads((AI/'eval/pose_segmentation_v0_report.json').read_text());assert aggregate['summaries']==summarize(reports)
    for f,h in aggregate['source_sha256'].items():assert hashlib.sha256((AI/'eval'/f).read_bytes()).hexdigest()==h
    assert aggregate['full_passes']==[r['passed'] for r in reports]
    assert aggregate['hardware_writes']==aggregate['physical_movements']==0 and not aggregate['qualification_installed']


def test_local_head_training_and_pose_export():
    import pytest
    if not (AI/'results/pose_segmentation_260926_control/training_model.pt').exists():pytest.skip('ignored training checkpoints not present')
    for seed in [260926,260927,260928]:
        torch.manual_seed(seed);initial=SegmentationPoseNet().state_dict()
        for arm in ['control','occlusion']:
            d=AI/f'results/pose_segmentation_{seed}_{arm}';full=torch.load(d/'training_model.pt',weights_only=True,map_location='cpu');pose=torch.load(d/'pose_model.pt',weights_only=True,map_location='cpu')
            assert all(torch.equal(value,full['backbone.'+key]) for key,value in pose.items())
            unchanged=all(torch.equal(initial[k],full[k]) for k in ['segmentation.weight','segmentation.bias'])
            assert unchanged==(arm=='control')
