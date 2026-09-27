"""Single selected fit and standalone parity on training images only."""
import hashlib,json,math,sys
from pathlib import Path
AI=Path(__file__).resolve().parents[1];ROOT=AI.parents[1];sys.path[:0]=[str(AI),str(AI.parent/'src')]
import numpy as np
import torch
from vision.pose_model import KeyboardPoseNet
from vision.linear_residual_pose import LinearResidualPoseNet
from vision.probe_linear_residual import fit_ridge,predict_ridge
from vision.landmark_occlusions import render_controlled
from vision.synthetic_keyboard import catalog_for_workspace
from vision.evaluate_dark_only_normalization import normalize


def run():
    p=AI/'train/grouped_linear_refit_v1_plan.json';plan=json.loads(p.read_text())
    for f,h in plan['file_sha256'].items():
        if hashlib.sha256((ROOT/f).read_bytes()).hexdigest()!=h:raise ValueError('source mismatch: '+f)
    out=AI/'eval/grouped_linear_refit_v1_report.json';directory=AI/'results/grouped_linear_refit_v1'
    if out.exists() or directory.exists():raise FileExistsError('existing evidence')
    selection=json.loads((ROOT/plan['selection_report']).read_text());assert selection['selected_alpha']==plan['alpha']==1.
    torch.set_num_threads(4);state=torch.load(ROOT/plan['checkpoint'],weights_only=True,map_location='cpu');base=KeyboardPoseNet().eval();base.load_state_dict(state)
    pixels=[];truth=[];first=None;catalog=catalog_for_workspace(ROOT)
    for seed in range(29000000,29000600):
        for c in plan['conditions']:
            image,label,_=render_controlled(seed,catalog,c,'rectangle')
            if first is None:first=image
            image,_=normalize(image);pose=label['pose'];pixels.append(np.asarray(image.resize((128,96))).transpose(2,0,1).copy())
            truth.append([(pose[0]-235)/30,(pose[1]-154)/24,(pose[2]-math.pi)/.2])
    pixels=np.stack(pixels);x=torch.from_numpy(pixels).float()/255;features=[];bases=[]
    with torch.no_grad():
        for batch in x.split(64):
            f=base.features[:4](batch);features.append(torch.nn.functional.adaptive_avg_pool2d(f,(4,4)).flatten(1));bases.append(base.head(base.features[4:](f)))
    features=torch.cat(features).numpy();bases=torch.cat(bases).numpy();fit=fit_ridge(features,np.array(truth)-bases,plan['alpha'])
    assert hashlib.sha256(pixels.tobytes()).hexdigest()==selection['pixel_sha256']['rectangle']
    model=LinearResidualPoseNet(state,fit,plan['file_sha256'][plan['selection_report']],plan['file_sha256'][plan['checkpoint']])
    expected=bases+predict_ridge(fit,features)
    with torch.no_grad():actual=torch.cat([model(b) for b in x.split(64)]).numpy()
    delta=float(np.max(np.abs(actual-expected)));assert delta<=plan['tolerance_normalized']
    directory.mkdir();artifact=directory/'model.pt';torch.save(model.export(),artifact)
    restored=LinearResidualPoseNet.from_export(torch.load(artifact,weights_only=True,map_location='cpu'))
    with torch.no_grad():loaded=torch.cat([restored(b) for b in x.split(64)]).numpy();single=model(x[:1])[0]
    assert np.array_equal(loaded,actual) and torch.equal(restored.predict_image(first),single)
    result=dict(plan_sha256=hashlib.sha256(p.read_bytes()).hexdigest(),alpha=plan['alpha'],fit=fit,training_images=len(x),training_groups=600,pixels_sha256=hashlib.sha256(pixels.tobytes()).hexdigest(),artifact=artifact.relative_to(ROOT).as_posix(),artifact_sha256=hashlib.sha256(artifact.read_bytes()).hexdigest(),artifact_bytes=artifact.stat().st_size,max_normalized_delta=delta,roundtrip_exact=True,image_preprocess_exact=True,reference_prediction_sha256=hashlib.sha256(expected.tobytes()).hexdigest(),export_prediction_sha256=hashlib.sha256(actual.tobytes()).hexdigest(),new_fits=1,hardware_writes=0,physical_movements=0,qualification_installed=False,limitations=['Training-image parity only; selection report digest identifies provenance, coefficients retained in this report.','No confirmation data or runtime installation; no coordinate uncertainty qualification.'])
    out.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n');print(json.dumps({k:v for k,v in result.items() if k!='fit'},indent=2))
if __name__=='__main__':run()
