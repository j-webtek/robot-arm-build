import hashlib,json,sys
from pathlib import Path
AI=Path(__file__).resolve().parents[1];ROOT=AI.parents[1];sys.path.insert(0,str(AI))
from train.train_pose_diversity import training_start
from evidence_artifacts import verify_frozen_artifacts
from vision.summarize_pose_diversity import summarize


def test_disjoint_candidate_and_repeated_control():
    plan={'training_groups':[29000000,600]}
    assert [training_start(plan,'control',e) for e in range(4)]==[29000000]*4
    starts=[training_start(plan,'occlusion',e) for e in range(4)]
    assert starts==[29000000,29000600,29001200,29001800]
    assert len({s+i for s in starts for i in range(600)})==2400


def test_budget_lineage_and_all_seed_aggregation():
    reports=[]
    for seed in [260926,260927,260928]:
        p=AI/f'train/pose_diversity_{seed}_plan.json';plan=json.loads(p.read_text());r=json.loads((AI/f'eval/pose_diversity_{seed}_report.json').read_text());reports.append(r)
        assert r['plan_sha256']==hashlib.sha256(p.read_bytes()).hexdigest()
        verify_frozen_artifacts(ROOT,plan['file_sha256'])
        for arm in ['control','occlusion']:
            result=r['results'][arm];e=result['training_evidence']
            assert len(e)==4 and sum(v['steps'] for v in e)==152
            assert result['total_training_presentations']==sum(v['images'] for v in e)==9600
            assert [v['start'] for v in e]==[training_start(plan,arm,i) for i in range(4)]
            assert len({v['pixels_sha256'] for v in e})==(1 if arm=='control' else 4)
            verify_frozen_artifacts(ROOT,{f'software/ai/results/pose_diversity_{seed}_{arm}/pose_model.pt':result['checkpoint_sha256']})
        a,b=[r['results'][arm]['training_evidence'][0] for arm in ['control','occlusion']]
        assert a['pixels_sha256']==b['pixels_sha256'] and a['teacher_sha256']==b['teacher_sha256']
    aggregate=json.loads((AI/'eval/pose_diversity_v0_report.json').read_text())
    for f,h in aggregate['source_sha256'].items():assert hashlib.sha256((AI/'eval'/f).read_bytes()).hexdigest()==h
    assert aggregate['summaries']==summarize(reports)
    assert aggregate['full_passes']==[r['passed'] for r in reports]
    assert aggregate['hardware_writes']==aggregate['physical_movements']==0 and not aggregate['qualification_installed']
