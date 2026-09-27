import hashlib,json,sys
from pathlib import Path
import numpy as np
import pytest
AI=Path(__file__).resolve().parents[1];ROOT=AI.parents[1];sys.path.insert(0,str(AI))
from vision.diagnose_residual_activations import summarize
from evidence_artifacts import verify_frozen_artifacts


def test_known_inactive_and_active_units():
    pre=np.array([[-1,1,0],[-2,2,3]],dtype=float);part=np.array([[1,2,3],[2,4,6]],dtype=float)
    result=summarize(pre,part,np.array([1,1,1]))
    assert result['inactive_unit_ids']==[0] and result['always_positive_unit_ids']==[1]
    assert result['positive_fraction']==[0,1,.5] and result['all_hidden_zero_images']==0
    assert result['feature_output_std_normalized']==[.5,1,1.5]
    assert result['residual_std_normalized']==result['feature_output_std_normalized']


def test_bias_only_output():
    r=summarize(-np.ones((4,32)),np.zeros((4,3)),np.array([1,2,3]))
    assert len(r['inactive_unit_ids'])==32 and r['all_hidden_zero_images']==4
    assert r['feature_output_exactly_zero'] and r['feature_output_std_normalized']==[0,0,0]
    assert r['output_bias_normalized']==[1,2,3]


@pytest.mark.parametrize('invalid',[np.ones((1,32)),np.full((4,32),np.nan)])
def test_invalid_activations_rejected(invalid):
    with pytest.raises(ValueError):summarize(invalid,np.zeros((len(invalid),3)),np.zeros(3))


def test_frozen_evidence_and_population():
    p=AI/'eval/residual_activations_v0_plan.json';plan=json.loads(p.read_text());verify_frozen_artifacts(ROOT,plan['file_sha256'])
    r=json.loads((AI/'eval/residual_activations_v0_report.json').read_text())
    assert r['plan_sha256']==hashlib.sha256(p.read_bytes()).hexdigest()
    old=json.loads((AI/'eval/residual_corrections_v0_report.json').read_text())
    assert r['training_pixels_sha256']==old['splits']['training']['pixels_sha256']
    assert {(x['seed'],x['mode']) for x in r['runs']}=={(s,m) for s in [260926,260927,260928] for m in ['constant','predicted']}
    for run in r['runs']:
        for phase in ['initial','trained']:
            a=run[phase];assert a['images']==2400 and a['hidden_units']==32
            assert a['inactive_unit_ids']==[i for i,p in enumerate(a['positive_fraction']) if p==0]
            assert a['always_positive_unit_ids']==[i for i,p in enumerate(a['positive_fraction']) if p==1]
        assert run['newly_inactive_ids']==sorted(set(run['trained']['inactive_unit_ids'])-set(run['initial']['inactive_unit_ids']))
        if len(run['trained']['inactive_unit_ids'])==32:
            assert run['trained']['all_hidden_zero_images']==2400 and run['trained']['feature_output_exactly_zero']
    assert r['optimizer_updates']==r['hardware_writes']==r['physical_movements']==0 and not r['qualification_installed']
