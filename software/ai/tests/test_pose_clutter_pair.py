import hashlib,json,sys
from pathlib import Path
import torch
AI=Path(__file__).resolve().parents[1];ROOT=AI.parents[1];sys.path.insert(0,str(AI))
from evidence_artifacts import verify_frozen_artifacts
from train.key_displacement_loss import key_loss
from vision.summarize_pose_clutter_pair import summarize


def test_consistency_symmetry_and_two_sided_gradients():
    a=torch.tensor([[.1,.2,.3]],requires_grad=True);b=torch.tensor([[.2,.1,.4]],requires_grad=True);offsets=torch.tensor([[10.,20.],[-30.,10.]])
    loss=key_loss(a,b,offsets)
    assert torch.allclose(loss,key_loss(b,a,offsets))
    loss.backward();assert a.grad.abs().sum()>0 and b.grad.abs().sum()>0
    assert key_loss(a,a,offsets).item()==0


def test_all_seed_pair_budgets_and_lineage():
    reports=[]
    for seed in [260926,260927,260928]:
        p=AI/f'train/pose_clutter_pair_{seed}_plan.json';plan=json.loads(p.read_text());r=json.loads((AI/f'eval/pose_clutter_pair_{seed}_report.json').read_text());reports.append(r)
        assert r['plan_sha256']==hashlib.sha256(p.read_bytes()).hexdigest();verify_frozen_artifacts(ROOT,plan['file_sha256'])
        a,b=[r['results'][arm] for arm in ['control','occlusion']]
        for k in ['training_pixels_sha256','clean_pixels_sha256','teacher_predictions_sha256']:assert a[k]==b[k]
        assert a['training_pixels_sha256']!=a['clean_pixels_sha256']
        for arm in ['control','occlusion']:
            result=r['results'][arm]
            assert result['training_pairs']==2400 and result['training_images']==4800 and result['total_presentations']==19200
            assert result['selected_epoch']==min(result['history'],key=lambda h:h['development_mse'])['epoch']
            verify_frozen_artifacts(ROOT,{f'software/ai/results/pose_clutter_pair_{seed}_{arm}/pose_model.pt':result['checkpoint_sha256']})
        old=json.loads((AI/'eval/pose_anchor_v0_report.json').read_text())
        assert r['development_pixels_sha256']==old['development_pixels_sha256']
    aggregate=json.loads((AI/'eval/pose_clutter_pair_v0_report.json').read_text())
    assert aggregate['summaries']==summarize(reports)
    for f,h in aggregate['source_sha256'].items():assert hashlib.sha256((AI/'eval'/f).read_bytes()).hexdigest()==h
    assert aggregate['full_passes']==[r['passed'] for r in reports]
    assert aggregate['hardware_writes']==aggregate['physical_movements']==0 and not aggregate['qualification_installed']
