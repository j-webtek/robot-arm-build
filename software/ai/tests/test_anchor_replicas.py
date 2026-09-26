import hashlib,json,sys
from pathlib import Path
AI=Path(__file__).resolve().parents[1];ROOT=AI.parents[1];sys.path.insert(0,str(AI))
from vision.summarize_anchor_replicas import summarize
from evidence_artifacts import verify_frozen_artifacts


def test_replica_inputs_and_fixed_parameters():
    original=json.loads((AI/'train/pose_anchor_v0_plan.json').read_text())
    for seed in [260927,260928]:
        path=AI/f'train/pose_anchor_replica_{seed}_plan.json';plan=json.loads(path.read_text());r=json.loads((AI/f'eval/pose_anchor_replica_{seed}_report.json').read_text())
        assert r['plan_sha256']==hashlib.sha256(path.read_bytes()).hexdigest()
        verify_frozen_artifacts(ROOT,plan['file_sha256'])
        for k in ['checkpoint','training_groups','development_groups','epochs','learning_rate','anchor_coefficient','selection','rule']:assert plan[k]==original[k]
        assert plan['seed']==seed
        a,b=r['results']['control'],r['results']['occlusion']
        for k in ['training_images','training_pixels_sha256','teacher_predictions_sha256','anchor_images']:assert a[k]==b[k]
        for arm in ['control','occlusion']:
            ck=AI/f'results/pose_anchor_replica_{seed}_{arm}/pose_model.pt'
            verify_frozen_artifacts(ROOT,{ck.relative_to(ROOT).as_posix():r['results'][arm]['checkpoint_sha256']})


def test_all_runs_retained_and_aggregate_recount():
    plan=json.loads((AI/'eval/pose_anchor_replication_v0_plan.json').read_text())
    for f,h in plan['source_sha256'].items():assert hashlib.sha256((ROOT/f).read_bytes()).hexdigest()==h
    r=json.loads((AI/'eval/pose_anchor_replication_v0_report.json').read_text());reports=[]
    for f,h in r['source_sha256'].items():
        p=AI/'eval'/f;assert hashlib.sha256(p.read_bytes()).hexdigest()==h;reports.append(json.loads(p.read_text()))
    assert len(reports)==3 and r['seeds']==[260926,260927,260928]
    assert r['summaries']==summarize(reports)
    assert r['full_passes']==[v['passed'] for v in reports]==[False]*3
    assert r['baseline_passes']==[True,True,False]
    assert r['hardware_writes']==r['physical_movements']==0 and not r['qualification_installed']
