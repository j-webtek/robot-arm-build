import hashlib,json,sys
from pathlib import Path
import numpy as np
AI=Path(__file__).resolve().parents[1];ROOT=AI.parents[1];sys.path.insert(0,str(AI))
from vision.diagnose_appearance_residual import compare


def test_known_broad_and_concentrated_changes():
    def row(error):return dict(mean_mm=error,translation_mm=error,rotation_only_maximum_mm=0.,translation_delta_mm=[error,0.])
    a={i:row(0.) for i in range(20)}
    b={i:row(1.) for i in range(20)}
    s=compare(a,b)['summary']
    assert s['worsened']==20 and s['mean_change_mm']==1
    assert s['top10_positive_share']==.5 and s['mean_change_excluding_top10_mm']==1
    b={i:row(1. if i==0 else 0.) for i in range(20)}
    s=compare(a,b)['summary']
    assert s['top10_positive_share']==1 and s['mean_change_excluding_top10_mm']==0
    assert compare(a,a)['summary']['top10_positive_share']==0


def test_frozen_report_recount():
    p=AI/'eval/appearance_residual_v0_plan.json';plan=json.loads(p.read_text());r=json.loads((AI/'eval/appearance_residual_v0_report.json').read_text())
    assert r['plan_sha256']==hashlib.sha256(p.read_bytes()).hexdigest()
    for f,h in plan['file_sha256'].items():assert hashlib.sha256((ROOT/f).read_bytes()).hexdigest()==h
    for comparison in r['comparisons'].values():
        rows=comparison['rows'];s=comparison['summary'];assert len(rows)==200
        delta=np.array([v['mean_change_mm'] for v in rows]);positive=np.maximum(delta,0);top=np.argsort(-positive)[:10]
        assert s['mean_change_mm']==float(delta.mean())
        assert s['worsened']==int((delta>0).sum())
        assert s['top10_positive_share']==float(positive[top].sum()/positive.sum())
        assert s['mean_change_excluding_top10_mm']==float(np.delete(delta,top).mean())
    assert r['hardware_writes']==r['physical_movements']==0
    assert not r['qualification_installed']
