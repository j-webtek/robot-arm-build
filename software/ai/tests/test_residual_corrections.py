import hashlib,json,sys
from pathlib import Path
import numpy as np
import pytest
AI=Path(__file__).resolve().parents[1];ROOT=AI.parents[1];sys.path.insert(0,str(AI))
from vision.diagnose_residual_corrections import correction_stats,training_offset
from evidence_artifacts import verify_frozen_artifacts


def test_known_scene_specific_and_constant_corrections():
    base=np.zeros((3,3));truth=np.array([[-1,-2,-3],[0,0,0],[1,2,3]],dtype=float)
    exact=correction_stats(base,truth,truth)
    assert all(v['correlation']==pytest.approx(1) and v['centered_energy_fraction']==pytest.approx(1) and v['residual_mse']==0 for v in exact.values())
    constant=correction_stats(base,np.ones((3,3)),truth)
    assert all(v['correlation'] is None and v['centered_energy_fraction']==0 for v in constant.values())
    assert constant['x_mm']['mean']==30 and constant['y_mm']['mean']==24


def test_offset_is_training_only_and_not_development_fit():
    base=np.zeros((3,3));train=np.array([[1,2,3],[2,4,6],[3,6,9]])
    offset=training_offset(base,train);assert np.array_equal(offset,[2,4,6])
    dev=np.zeros((3,3));stats=correction_stats(base,base+offset,dev)
    assert stats['x_mm']['residual_mse']==3600 and stats['x_mm']['baseline_mse']==0


@pytest.mark.parametrize('bad',[np.zeros((1,3)),np.zeros((3,2)),np.full((3,3),np.nan)])
def test_invalid_arrays_rejected(bad):
    with pytest.raises(ValueError):correction_stats(bad,bad,bad)


def test_report_lineage_and_energy_identity():
    p=AI/'eval/residual_corrections_v0_plan.json';plan=json.loads(p.read_text());verify_frozen_artifacts(ROOT,plan['file_sha256'])
    r=json.loads((AI/'eval/residual_corrections_v0_report.json').read_text());assert r['plan_sha256']==hashlib.sha256(p.read_bytes()).hexdigest()
    assert r['splits']['training']['images']==2400 and r['splits']['development']['images']==800 and len(r['runs'])==6
    previous=json.loads((AI/'eval/pose_mask_residual_260926_report.json').read_text())
    assert r['splits']['training']['pixels_sha256']==previous['results']['control']['training_pixels_sha256']
    assert r['splits']['development']['pixels_sha256']==previous['development_pixels_sha256']
    assert {(v['seed'],v['mode']) for v in r['runs']}=={(s,m) for s in [260926,260927,260928] for m in ['constant','predicted']}
    for run in r['runs']:
        for split in run['splits'].values():
            for v in split['stats'].values():
                assert v['baseline_mse']==pytest.approx(v['needed_mean']**2+v['needed_std']**2)
                assert v['residual_mse']==pytest.approx(v['centered_residual_mse']+(v['needed_mean']-v['mean'])**2)
    assert r['optimizer_updates']==r['hardware_writes']==r['physical_movements']==0 and not r['qualification_installed']
