import hashlib,json,sys
from pathlib import Path
import numpy as np
import pytest
from PIL import Image
AI=Path(__file__).resolve().parents[1];ROOT=AI.parents[1];sys.path.insert(0,str(AI))
from vision.image_quality_scale import features,fit_scale,predict_scale
from evidence_artifacts import verify_frozen_artifacts


def test_image_features_are_finite_and_respond_to_brightness_and_edges():
    black=features(Image.new('RGB',(128,96),(0,0,0)));white=features(Image.new('RGB',(128,96),(255,255,255)))
    assert black.shape==white.shape==(56,) and np.isfinite(black).all()
    assert black[0]==0 and white[0]==pytest.approx(1.)
    assert black[4]==1 and white[5]==1
    stripes=np.zeros((96,128,3),dtype=np.uint8);stripes[:,::2]=255
    assert features(Image.fromarray(stripes))[6]>white[6]
    with pytest.raises(ValueError):features(Image.new('L',(128,96)))


def test_fit_uses_only_supplied_rows_and_outputs_positive_scales():
    rng=np.random.default_rng(7);x=rng.normal(size=(20,56));errors=np.arange(20)/10
    fit=fit_scale(x[:16],errors[:16]);x[16:]=1000;errors[16:]=1000
    assert fit==fit_scale(x[:16],errors[:16])
    assert np.allclose(fit['mean'],x[:16].mean(0))
    pred=predict_scale(fit,x[16:]);assert np.all(pred>=.1) and np.all(pred<=20.)
    with pytest.raises(ValueError):fit_scale(x,np.full(20,-1))
    with pytest.raises(ValueError):predict_scale(fit,np.full((1,56),np.nan))


def test_training_report_population_folds_and_metrics():
    p=AI/'train/image_quality_scale_v1_plan.json';plan=json.loads(p.read_text());verify_frozen_artifacts(ROOT,plan['file_sha256'])
    r=json.loads((AI/'eval/image_quality_scale_v1_report.json').read_text());assert r['plan_sha256']==hashlib.sha256(p.read_bytes()).hexdigest()
    rows=r['rows'];expected={(s,t,c) for s in range(33000000,33000600) for t in plan['styles'] for c in plan['conditions']}
    assert len(rows)==4800 and {(v['seed'],v['style'],v['condition']) for v in rows}==expected
    folds=r['fold_fits'];validation=[s for f in folds for s in f['validation_seeds']]
    assert len(validation)==len(set(validation))==600 and set(validation)==set(range(33000000,33000600))
    for f in folds:
        assert f['training_rows']==3840 and f['validation_rows']==960
        assert len(f['validation_seeds'])==120 and f['fit']['alpha']==1.
        assert len(f['fit']['weights'])==56 and min(f['fit']['scale'])>0
        constant=float(np.clip(np.exp(f['fit']['intercept']),.1,20))
        assert all(v['constant_scale_mm']==constant for v in rows if v['seed'] in f['validation_seeds'])
    for c in plan['conditions']:
        subset=[v for v in rows if v['condition']==c];truth=np.log([v['error_mm']+.1 for v in subset])
        assert r['summaries'][c]==dict(images=1200,scale_log_mse=float(np.mean((np.log([v['scale_mm'] for v in subset])-truth)**2)),constant_log_mse=float(np.mean((np.log([v['constant_scale_mm'] for v in subset])-truth)**2)))
    assert r['passed']==all(v['scale_log_mse']<v['constant_log_mse'] for v in r['summaries'].values())
    assert r['uncertainty_fits']==5 and r['pose_fits']==r['calibration_fits']==r['hardware_writes']==r['physical_movements']==0
    assert not r['qualification_installed']
