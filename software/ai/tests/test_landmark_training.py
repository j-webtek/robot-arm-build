import hashlib,json,sys
from pathlib import Path
import numpy as np
AI=Path(__file__).resolve().parents[1];ROOT=AI.parents[1]
sys.path[:0]=[str(AI),str(AI.parent/'src')]
from vision.landmark_occlusions import render_controlled
from vision.landmark_renderer import render_landmarks
from vision.synthetic_keyboard import catalog_for_workspace


def test_controlled_masks_and_baseline_preservation():
    catalog=catalog_for_workspace(ROOT)
    for seed in range(15000000,15000012):
        base,label,mask=render_landmarks(seed,catalog)
        untouched,_,_=render_controlled(seed,catalog,'standard')
        assert base.tobytes()==untouched.tobytes()
        for style in ('rectangle','ellipse'):
            image,full,newmask=render_controlled(seed,catalog,'full',style)
            assert full['landmarks'][seed%4]['unoccluded_fraction']==0
            assert full['pose']==label['pose']
            assert np.all(np.asarray(newmask)>=np.asarray(mask))
            _,partial,_=render_controlled(seed,catalog,'partial',style)
            assert partial['landmarks'][seed%4]['unoccluded_fraction']<1


def test_training_evidence():
    path=AI/'train/landmark_v0_plan.json';m=json.loads(path.read_text())
    r=json.loads((AI/'eval/landmark_v0_scorecard.json').read_text())
    assert hashlib.sha256(path.read_bytes()).hexdigest()==r['plan_sha256']
    for f,h in m['file_sha256'].items():assert hashlib.sha256((ROOT/f).read_bytes()).hexdigest()==h
    assert r['training_images']==2400 and r['development_images']==800
    assert len(r['history'])==8
    assert r['selected_epoch']==min(r['history'],key=lambda e:e['development_loss'])['epoch']
    hidden=[(t,p) for c in r['cases'] for t,p in zip(c['visibility_targets'],c['visibility_probabilities']) if t==0]
    assert len(hidden)==r['fully_occluded_corners']
    assert sum(p>=.5 for _,p in hidden)==r['false_visible_occluded']
    for condition in m['conditions']:
        rows=[c for c in r['cases'] if c['condition']==condition]
        assert [c['seed'] for c in rows]==list(range(15000000,15000200))
        for arm in ('baseline','landmark'):
            assert abs(np.mean([c['arms'][arm]['mean_mm'] for c in rows])-r['summaries'][condition][arm]['mean_mm'])<1e-10
            assert sum(c['arms'][arm]['maximum_mm']>3 for c in rows)==r['summaries'][condition][arm]['tail']
    assert r['comparison_passed']==all(all(c.values()) for c in r['checks'].values())
    assert r['hardware_writes']==r['physical_movements']==0 and not r['qualification_installed']
