import hashlib,json,math,sys
from pathlib import Path
import numpy as np
import pytest
AI=Path(__file__).resolve().parents[1];ROOT=AI.parents[1];sys.path.insert(0,str(AI))
from vision.audit_scene_splits import group_folds
from vision.scene_pose_bins import pose_bins
from evidence_artifacts import verify_frozen_artifacts


def test_scene_group_folds_are_balanced_disjoint_and_order_independent():
    seeds=list(range(29000000,29000600));folds=group_folds(seeds)
    assert folds==group_folds(reversed(seeds))
    assert sorted(s for f in folds for s in f)==seeds
    for fold in folds:
        assert len(fold)==120
        assert [sum(s%4==c for s in fold) for c in range(4)]==[30]*4
        assert not set(fold)&(set(seeds)-set(fold))


@pytest.mark.parametrize('seeds',[[],[1,1],[True],[1.5]])
def test_invalid_scene_groups_rejected(seeds):
    with pytest.raises(ValueError):group_folds(seeds)


def test_fixed_pose_bin_support():
    assert pose_bins([[205,130,math.pi-math.radians(11)],[265,178,math.pi+math.radians(11)]])==[0,124]
    for pose in [[204,130,math.pi],[235,154,float('nan')],[235,179,math.pi]]:
        with pytest.raises(ValueError):pose_bins([pose])


def test_audit_lineage_population_and_overlap_recount():
    p=AI/'eval/scene_split_audit_v0_plan.json';plan=json.loads(p.read_text());verify_frozen_artifacts(ROOT,plan['file_sha256'])
    r=json.loads((AI/'eval/scene_split_audit_v0_report.json').read_text())
    assert r['plan_sha256']==hashlib.sha256(p.read_bytes()).hexdigest()
    pixels={};scene_sets={}
    for name,spec in plan['cohorts'].items():
        c=r['cohorts'][name];start,count=spec['groups'];rows=c['rows']
        assert len(rows)==count*4
        assert {(v['seed'],v['condition']) for v in rows}=={(s,k) for s in range(start,start+count) for k in plan['conditions']}
        scene_sets[name]={v['seed'] for v in rows}
        poses=[]
        for seed in sorted(scene_sets[name]):
            group=[v for v in rows if v['seed']==seed]
            assert len({tuple(v['pose']) for v in group})==1
            poses.append(group[0]['pose'])
        counts=np.bincount(pose_bins(poses),minlength=125)
        assert counts.tolist()==c['pose_bin_counts']
        assert int((counts>0).sum())==c['occupied_pose_bins']
        prior=json.loads((ROOT/spec['evidence']).read_text())
        assert c['pixels_sha256']==(prior['splits'][name]['pixels_sha256'] if name!='consumed_evaluation' else prior['pixels_sha256'])
        for v in rows:pixels.setdefault(v['pixels_sha256'],set()).add(name)
    assert not any(len(v)>1 for v in pixels.values())
    for pair,overlap in r['scene_overlap'].items():
        a,b=pair.split('__');assert overlap==sorted(scene_sets[a]&scene_sets[b])==[]
    assert r['cross_cohort_exact_pixel_duplicates']==[]
    assert r['validation_scene_folds']==group_folds(sorted(scene_sets['training']))
    assert r['new_fits']==r['hardware_writes']==r['physical_movements']==0
    protocol=json.loads((AI/'eval/grouped_linear_selection_v1_protocol.json').read_text())
    assert protocol['audit_sha256']==hashlib.sha256((AI/'eval/scene_split_audit_v0_report.json').read_bytes()).hexdigest()
    assert protocol['validation_scene_folds']==r['validation_scene_folds']
    assert protocol['status']=='specified_not_executed'
