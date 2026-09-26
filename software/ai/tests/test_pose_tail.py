import hashlib,json,math,sys
from pathlib import Path
from types import SimpleNamespace
import pytest
AI=Path(__file__).resolve().parents[1];ROOT=AI.parents[1];sys.path.insert(0,str(AI))
from vision.diagnose_pose_tail import decompose


def test_known_translation_and_rotation():
    targets=[SimpleNamespace(center=SimpleNamespace(x=252.5,y=158.5))]
    truth=[235,154,0]
    r=decompose([238,158,0],truth,targets)
    assert r['translation_mm']==r['maximum_mm']==5
    assert r['rotation_only_maximum_mm']==0
    r=decompose([235,154,math.pi/2],truth,targets)
    assert r['translation_mm']==0
    assert r['rotation_only_maximum_mm']==pytest.approx(10*math.sqrt(2))
    assert r['maximum_mm']==r['rotation_only_maximum_mm']


def test_report_reproduction_and_pairs():
    p=AI/'eval/pose_tail_v0_plan.json';plan=json.loads(p.read_text());report=json.loads((AI/'eval/pose_tail_v0_report.json').read_text())
    assert report['plan_sha256']==hashlib.sha256(p.read_bytes()).hexdigest()
    for f,h in plan['file_sha256'].items():assert hashlib.sha256((ROOT/f).read_bytes()).hexdigest()==h
    source=json.loads((AI/'eval/pose_landmark_v0_report.json').read_text())
    assert report['development_pixels_sha256']==source['development_pixels_sha256']
    assert len(report['rows'])==800
    for row,old in zip(report['rows'],source['rows']):
        assert (row['seed'],row['condition'])==(old['seed'],old['condition'])
        for k,v in old['arms']['pose'].items():assert row[k]==pytest.approx(v,abs=1e-9)
        assert row['maximum_mm']<=row['translation_mm']+row['rotation_only_maximum_mm']+1e-9
    baseline={r['seed'] for r in report['rows'] if r['condition']=='standard' and r['maximum_mm']>3}
    for c,summary in report['summaries'].items():
        bad={r['seed'] for r in report['rows'] if r['condition']==c and r['maximum_mm']>3}
        assert set(summary['new_bad_vs_standard'])==bad-baseline
        assert set(summary['recovered_vs_standard'])==baseline-bad
    assert report['hardware_writes']==report['physical_movements']==0
    assert not report['qualification_installed']
