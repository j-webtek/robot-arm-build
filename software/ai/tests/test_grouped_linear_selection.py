import hashlib,json,sys
from pathlib import Path
import numpy as np
import pytest
AI=Path(__file__).resolve().parents[1];ROOT=AI.parents[1];sys.path.insert(0,str(AI))
from train.select_grouped_linear import fold_indices,select_candidate
from vision.probe_linear_residual import fit_ridge,predict_ridge
from vision.evaluate_linear_fresh import checks_for
from evidence_artifacts import verify_frozen_artifacts


def test_fold_fit_ignores_validation_features_and_labels():
    seeds=[1,1,2,2,3,3];ti,vi=fold_indices(seeds,[2])
    assert ti.tolist()==[0,1,4,5] and vi.tolist()==[2,3]
    x=np.arange(12,dtype=float).reshape(6,2);y=np.arange(18,dtype=float).reshape(6,3)
    fit=fit_ridge(x[ti],y[ti],1.)
    x[vi]=1e9;y[vi]=-1e9
    assert fit==fit_ridge(x[ti],y[ti],1.)
    assert np.allclose(fit['mean'],x[ti].mean(0))
    assert np.isfinite(predict_ridge(fit,x[vi])).all()
    with pytest.raises(ValueError):fold_indices(seeds,[])
    with pytest.raises(ValueError):fold_indices(seeds,[1,2,3])


def test_selection_rejects_all_and_uses_fixed_tiebreak():
    def item(a,tail,mean,passed=True):return dict(alpha=a,passed=passed,summary={'standard':dict(tail=tail,mean_mm=mean)})
    assert select_candidate([item(1,0,0,False)]) is None
    assert select_candidate([item(.01,1,1),item(1,1,1)])==1
    assert select_candidate([item(.01,1,.9),item(1,1,1)])==.01
    assert select_candidate([item(.01,0,2),item(1,1,1)])==.01


def test_frozen_report_group_membership_and_metric_recount():
    path=AI/'train/grouped_linear_v1_plan.json';plan=json.loads(path.read_text());verify_frozen_artifacts(ROOT,plan['file_sha256'])
    protocol=json.loads((ROOT/plan['protocol']).read_text());r=json.loads((AI/'eval/grouped_linear_v1_report.json').read_text())
    assert r['plan_sha256']==hashlib.sha256(path.read_bytes()).hexdigest()
    population={(s,c) for s in range(29000000,29000600) for c in protocol['conditions']}
    def recount(rows,summary):
        assert len(rows)==2400 and {(v['seed'],v['condition']) for v in rows}==population
        for c in protocol['conditions']:
            group=[v for v in rows if v['condition']==c]
            assert summary[c]==dict(cases=600,mean_mm=float(np.mean([v['mean_mm'] for v in group])),tail=sum(v['maximum_mm']>3 for v in group),yaw_p95=float(np.percentile([v['yaw_degrees'] for v in group],95)))
    recount(r['baseline_rows'],r['baseline_summary'])
    assert [v['alpha'] for v in r['runs']]==protocol['ridge_alphas']
    for run in r['runs']:
        recount(run['rows'],run['summary']);checks,passed=checks_for(r['baseline_summary'],run['summary'])
        assert (checks,passed)==(run['checks'],run['passed'])
        all_val=[]
        for i,f in enumerate(run['fold_fits']):
            train=set(f['training_seeds']);val=set(f['validation_seeds']);all_val+=f['validation_seeds']
            assert f['validation_seeds']==protocol['validation_scene_folds'][i]
            assert not train&val and train|val==set(range(29000000,29000600))
            assert len(train)==480 and len(val)==120
            assert f['training_rows']==1920 and f['validation_rows']==480
            assert f['fit']['alpha']==run['alpha'] and min(f['fit']['scale'])>0
            assert f['fit']['normal_equation_max_residual']<1e-10
        assert sorted(all_val)==list(range(29000000,29000600))
    assert r['selected_alpha']==select_candidate(r['runs'])==1.
    assert r['closed_form_fits']==20 and r['final_fits']==r['hardware_writes']==r['physical_movements']==0
    assert not r['qualification_installed']
