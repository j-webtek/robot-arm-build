import hashlib,json,sys
from pathlib import Path
import numpy as np
AI=Path(__file__).resolve().parents[1];ROOT=AI.parents[1];sys.path.insert(0,str(AI))
from train.train_pose_anchor import conditions
from evidence_artifacts import verify_frozen_artifacts


def test_projection_loss_and_gradients():
    import torch
    from train.key_displacement_loss import project_keys,key_loss
    from vision.synthetic_keyboard import transform_target
    from vision.train_pose import _pose_from_prediction
    assert conditions('control')==conditions('occlusion')
    pose=torch.tensor([[.2,-.3,.4]],dtype=torch.float64,requires_grad=True)
    offsets=torch.tensor([[10.,20.],[-30.,5.]],dtype=torch.float64)
    expected=[transform_target(float(x)+242.5,float(y)+158.5,_pose_from_prediction(pose.detach()[0])[:2],_pose_from_prediction(pose.detach()[0])[2]) for x,y in offsets]
    assert np.allclose(project_keys(pose,offsets).detach().numpy()[0],expected)
    truth=torch.zeros_like(pose)
    assert key_loss(truth,truth,offsets).item()==0
    shift=torch.tensor([[.1,0.,0.]],dtype=torch.float64)
    assert abs(key_loss(shift,truth,offsets).item()-.01)<1e-12
    assert torch.autograd.gradcheck(lambda x:key_loss(x,truth,offsets),(pose,))


def test_report_metrics_selection_and_frozen_checks():
    p=AI/'train/pose_anchor_v0_plan.json';plan=json.loads(p.read_text());r=json.loads((AI/'eval/pose_anchor_v0_report.json').read_text())
    assert r['plan_sha256']==hashlib.sha256(p.read_bytes()).hexdigest()
    plan_artifacts=verify_frozen_artifacts(ROOT,plan['file_sha256'])
    external_artifacts={a.relative_path:a.sha256 for a in plan_artifacts if a.relative_path.startswith('software/ai/results/')}
    assert external_artifacts=={'software/ai/results/translation_weighted_v0_translation_weighted/pose_model.pt':'0fd4ee3edd1dc6e0068c6e1530fdf7017a77a3e7841334682272e99aa344125d'}
    result_checkpoints={}
    for arm,result in r['results'].items():
        assert len(result['rows'])==800
        for c,m in result['summaries'].items():
            rows=[v for v in result['rows'] if v['condition']==c]
            assert m['mean_mm']==float(np.mean([v['mean_mm'] for v in rows]))
            assert m['tail']==sum(v['maximum_mm']>3 for v in rows)
            assert m['yaw_p95']==float(np.percentile([v['yaw_degrees'] for v in rows],95))
        if arm!='baseline':
            assert result['training_images']==2400
            assert result['selected_epoch']==min(result['history'],key=lambda h:h['development_mse'])['epoch']
            ck='software/ai/results/pose_anchor_v0_'+arm+'/pose_model.pt'
            result_checkpoints[ck]=result['checkpoint_sha256']
    checkpoint_status=verify_frozen_artifacts(ROOT,result_checkpoints)
    assert {a.relative_path:a.sha256 for a in checkpoint_status}==result_checkpoints
    for ref,checks in r['checks'].items():
        for c in plan['conditions']:
            a=r['results'][ref]['summaries'][c];b=r['results']['occlusion']['summaries'][c]
            assert checks[c]==dict(mean=b['mean_mm']<=a['mean_mm'],tail=b['tail']<=a['tail'],yaw=b['yaw_p95']<=1.1*a['yaw_p95'])
    assert r['results']['control']['training_pixels_sha256']==r['results']['occlusion']['training_pixels_sha256']
    assert r['results']['control']['teacher_predictions_sha256']==r['results']['occlusion']['teacher_predictions_sha256']
    assert all(r['results'][a]['anchor_images']==1200 for a in ['control','occlusion'])
    assert r['passed'] is False
    assert r['hardware_writes']==r['physical_movements']==0
    assert not r['qualification_installed']


def test_anchor_mask_and_detached_teacher():
    import torch
    from train.train_pose_anchor import anchor_loss
    pred=torch.tensor([[.1,0.,0.],[2.,2.,2.]],requires_grad=True)
    teacher=torch.zeros_like(pred,requires_grad=True)
    offsets=torch.tensor([[10.,20.]])
    loss=anchor_loss(pred,teacher,torch.tensor([True,False]),offsets)
    assert abs(float(loss.detach())-.01)<1e-6
    loss.backward()
    assert teacher.grad is None
    assert pred.grad[1].abs().sum()==0
    pred.grad=None
    anchor_loss(pred,teacher,torch.tensor([False,False]),offsets).backward()
    assert pred.grad.abs().sum()==0
