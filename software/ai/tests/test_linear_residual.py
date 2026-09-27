import hashlib,json,sys
from pathlib import Path
import numpy as np
import pytest
AI=Path(__file__).resolve().parents[1];ROOT=AI.parents[1];sys.path.insert(0,str(AI))
from vision.probe_linear_residual import fit_ridge,predict_ridge
from evidence_artifacts import verify_frozen_artifacts


def test_known_ridge_solution_with_unpenalized_intercept():
    x=np.array([[-1.,7.],[1.,7.]]);y=np.array([[3.,2.,1.],[5.,6.,7.]])
    fit=fit_ridge(x,y,.01)
    assert np.allclose(fit['weights'][0],np.array([1.,2.,3.])/1.01)
    assert fit['weights'][1]==[0,0,0] and fit['constant_columns']==1
    assert fit['intercept']==[4,4,4]
    assert fit['normal_equation_max_residual']<1e-12
    assert np.allclose(predict_ridge(fit,x).mean(0),y.mean(0))


def test_inference_uses_training_normalization_only():
    fit=fit_ridge(np.array([[-1.],[1.]]),np.array([[-1.,-1.,-1.],[1.,1.,1.]]),.01)
    before=json.dumps(fit,sort_keys=True)
    assert np.allclose(predict_ridge(fit,[[10.],[20.]]),np.array([[10.]*3,[20.]*3])/1.01)
    assert json.dumps(fit,sort_keys=True)==before


@pytest.mark.parametrize('alpha',[0,-1,float('nan')])
def test_invalid_regularization_rejected(alpha):
    with pytest.raises(ValueError):fit_ridge(np.ones((2,3)),np.zeros((2,3)),alpha)


def test_frozen_report_and_acceptance_recount():
    p=AI/'eval/linear_residual_v0_plan.json';plan=json.loads(p.read_text());verify_frozen_artifacts(ROOT,plan['file_sha256'])
    r=json.loads((AI/'eval/linear_residual_v0_report.json').read_text())
    assert r['plan_sha256']==hashlib.sha256(p.read_bytes()).hexdigest()
    prior=json.loads((AI/'eval/residual_corrections_v0_report.json').read_text())
    for split in ['training','development']:assert r['splits'][split]['pixels_sha256']==prior['splits'][split]['pixels_sha256']
    assert len(r['runs'])==4 and r['runs'][0]['name']=='constant_control'
    for run in r['runs']:
        fit=run['fit'];assert fit['alpha']==.01 and len(fit['mean'])==len(fit['scale'])==len(fit['weights'])==512
        assert fit['normal_equation_max_residual']<1e-10
        assert np.isfinite(fit['regularized_condition_number']) and all(s>0 for s in fit['scale'])
    for run in r['runs'][1:]:
        candidate=run['splits']['development']['score']
        for ref,base in [('baseline',r['splits']['development']['baseline_score']),('control',r['runs'][0]['splits']['development']['score'])]:
            for c in plan['conditions']:
                a,b=candidate[c],base[c]
                assert run['checks'][ref][c]==dict(mean=a['mean_mm']<=b['mean_mm'],tail=a['tail']<=b['tail'],yaw=a['yaw_p95']<=1.1*b['yaw_p95'])
            assert run['checks'][ref]['occlusion_tail_improves']==(sum(candidate[c]['tail'] for c in ['partial','full'])<sum(base[c]['tail'] for c in ['partial','full']))
        assert run['passed']==all(all(all(v.values()) if isinstance(v,dict) else v for v in ref.values()) for ref in run['checks'].values())
    assert r['closed_form_fits']==4 and r['optimizer_updates']==r['hardware_writes']==r['physical_movements']==0
    assert not r['qualification_installed']
