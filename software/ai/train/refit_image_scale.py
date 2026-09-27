"""One final uncertainty-scale fit, preserving feature/input lineage."""
import hashlib,json,sys
from pathlib import Path
AI=Path(__file__).resolve().parents[1];ROOT=AI.parents[1];sys.path[:0]=[str(AI),str(AI.parent/'src')]
import numpy as np
from vision.image_quality_scale import features,fit_scale,predict_scale
from vision.image_scale_export import validate,predict_image,SCHEMA,PREPROCESS
from vision.landmark_occlusions import render_controlled
from vision.synthetic_keyboard import catalog_for_workspace


def run():
    p=AI/'train/image_scale_refit_v1_plan.json';plan=json.loads(p.read_text())
    for f,h in plan['file_sha256'].items():
        if hashlib.sha256((ROOT/f).read_bytes()).hexdigest()!=h:raise ValueError('source mismatch: '+f)
    out=AI/'eval/image_scale_refit_v1_report.json';artifact_path=AI/'eval/image_scale_refit_v1_model.json'
    if out.exists() or artifact_path.exists():raise FileExistsError('existing evidence')
    source=json.loads((ROOT/plan['source']).read_text());assert source['passed'];catalog=catalog_for_workspace(ROOT);images=[];x=[]
    for row in source['rows']:
        image,_,_=render_controlled(row['seed'],catalog,row['condition'],row['style']);images.append(image);x.append(features(image))
    x=np.stack(x);assert hashlib.sha256(x.tobytes()).hexdigest()==source['features_sha256']
    fit=fit_scale(x,[r['error_mm'] for r in source['rows']],1.)
    artifact=validate(dict(schema=SCHEMA,preprocess=PREPROCESS,pose_sha256=plan['pose_sha256'],source_sha256=plan['file_sha256'][plan['source']],feature_source_sha256=plan['file_sha256']['software/ai/vision/image_quality_scale.py'],fit=fit))
    payload=json.dumps(artifact,indent=2,allow_nan=False)+'\n';loaded=validate(json.loads(payload))
    expected=predict_scale(fit,x);restored=predict_scale(loaded['fit'],x);single=np.array([predict_image(loaded,i) for i in images])
    assert np.array_equal(expected,restored);delta=float(np.max(np.abs(expected-single)));assert delta<=1e-12
    artifact_path.write_text(payload)
    result=dict(plan_sha256=hashlib.sha256(p.read_bytes()).hexdigest(),artifact=artifact_path.relative_to(ROOT).as_posix(),artifact_sha256=hashlib.sha256(artifact_path.read_bytes()).hexdigest(),artifact_bytes=artifact_path.stat().st_size,images=len(x),features_sha256=source['features_sha256'],scale_predictions_sha256=hashlib.sha256(expected.tobytes()).hexdigest(),roundtrip_exact=True,image_max_delta_mm=delta,scale_fits=1,pose_fits=0,calibration_fits=0,hardware_writes=0,physical_movements=0,qualification_installed=False)
    out.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
if __name__=='__main__':run()
