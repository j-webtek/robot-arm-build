import hashlib,json,sys
from pathlib import Path
import numpy as np
AI=Path(__file__).resolve().parents[1];ROOT=AI.parents[1];sys.path[:0]=[str(AI),str(AI.parent/'src')]
from evidence_artifacts import verify_frozen_artifacts
from vision.clutter_ablation_occlusions import render_controlled
from vision.landmark_occlusions import render_controlled as original
from vision.synthetic_keyboard import catalog_for_workspace


def test_renderer_original_identity_and_pose_invariance():
    catalog=catalog_for_workspace(ROOT)
    for seed in [15000027,15000068,15000083,15000144,15000171]:
        for condition in ['standard','appearance_shift','partial','full']:
            image,label,mask=original(seed,catalog,condition,'ellipse')
            for removed in [frozenset(),frozenset(['arm']),frozenset(['ruler']),frozenset(['arm','ruler'])]:
                actual,lab,newmask=render_controlled(seed,catalog,condition,'ellipse',removed)
                assert lab['pose']==label['pose']
                assert [(v['x_px'],v['y_px']) for v in lab['landmarks']]==[(v['x_px'],v['y_px']) for v in label['landmarks']]
                assert np.all(np.asarray(newmask)<=np.asarray(mask))
                if not removed:assert actual.tobytes()==image.tobytes() and lab==label and newmask.tobytes()==mask.tobytes()


def test_retained_clutter_report_recount():
    p=AI/'eval/clutter_ablation_v0_plan.json';plan=json.loads(p.read_text());r=json.loads((AI/'eval/clutter_ablation_v0_report.json').read_text())
    assert r['plan_sha256']==hashlib.sha256(p.read_bytes()).hexdigest();verify_frozen_artifacts(ROOT,plan['file_sha256'])
    assert len(r['rows'])==800
    for mode,conditions in r['summaries'].items():
        for c,m in conditions.items():
            rows=[v for v in r['rows'] if v['condition']==c]
            assert m['tail']==sum(v['modes'][mode]['maximum_mm']>3 for v in rows)
            assert m['recovered']==sum(v['modes']['original']['maximum_mm']>3 and v['modes'][mode]['maximum_mm']<=3 for v in rows)
            assert m['introduced']==sum(v['modes']['original']['maximum_mm']<=3 and v['modes'][mode]['maximum_mm']>3 for v in rows)
            assert m['persistent_remaining']==sum(v['persistent'] and v['modes'][mode]['maximum_mm']>3 for v in rows)
    assert r['hardware_writes']==r['physical_movements']==0 and not r['qualification_installed']
