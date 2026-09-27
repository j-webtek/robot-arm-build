"""Freeze selected diagnostic coefficients and verify existing-development parity."""
import hashlib,json,sys,time,statistics
from pathlib import Path
AI=Path(__file__).resolve().parents[1];ROOT=AI.parents[1];sys.path[:0]=[str(AI),str(AI.parent/'src')]
import numpy as np
import torch
from torch.nn import functional as F
from vision.linear_residual_pose import LinearResidualPoseNet
from vision.probe_linear_residual import predict_ridge
from vision.landmark_occlusions import render_controlled
from vision.synthetic_keyboard import catalog_for_workspace
from vision.evaluate_dark_only_normalization import normalize


def timing(model,x):
    with torch.no_grad():
        for _ in range(10):model(x)
        values=[]
        for _ in range(100):
            start=time.perf_counter_ns();model(x);values.append((time.perf_counter_ns()-start)/1e6)
    return dict(median_ms=statistics.median(values),p95_ms=float(np.percentile(values,95)),iterations=100,warmup=10,batch=1)


def run():
    p=AI/'eval/linear_export_v0_plan.json';plan=json.loads(p.read_text())
    for f,h in plan['file_sha256'].items():
        if hashlib.sha256((ROOT/f).read_bytes()).hexdigest()!=h:raise ValueError('source changed: '+f)
    out=AI/'eval/linear_export_v0_report.json';directory=AI/'results/linear_residual_export_v0'
    if out.exists() or directory.exists():raise FileExistsError('existing export evidence')
    source=json.loads((ROOT/plan['source_report']).read_text());fit=source['runs'][0]['fit'];assert source['runs'][0]['name']=='constant_control'
    torch.set_num_threads(4)
    model=LinearResidualPoseNet(torch.load(ROOT/plan['checkpoint'],map_location='cpu',weights_only=True),fit,plan['file_sha256'][plan['source_report']],plan['file_sha256'][plan['checkpoint']])
    catalog=catalog_for_workspace(ROOT);pixels=[];first=None
    for seed in range(15000000,15000200):
        for c in plan['conditions']:
            image,_,_=render_controlled(seed,catalog,c,'ellipse')
            if first is None:first=image
            image,_=normalize(image);pixels.append(np.asarray(image.resize((128,96))).transpose(2,0,1).copy())
    pixels=np.stack(pixels);x=torch.from_numpy(pixels).float()/255
    expected=[];actual=[]
    with torch.no_grad():
        for batch in x.split(64):
            f=model.backbone.features[:4](batch);base=model.backbone.head(model.backbone.features[4:](f));d=F.adaptive_avg_pool2d(f,(4,4)).flatten(1)
            expected.append(base.numpy()+predict_ridge(fit,d.numpy()));actual.append(model(batch).numpy())
    expected=np.concatenate(expected);actual=np.concatenate(actual);delta=float(np.max(np.abs(actual-expected)))
    assert delta<=plan['tolerance_normalized']
    assert hashlib.sha256(expected.tobytes()).hexdigest()==source['runs'][0]['splits']['development']['predictions_sha256']
    assert hashlib.sha256(pixels.tobytes()).hexdigest()==source['splits']['development']['pixels_sha256']
    directory.mkdir();path=directory/'model.pt';torch.save(model.export(),path)
    restored=LinearResidualPoseNet.from_export(torch.load(path,map_location='cpu',weights_only=True))
    with torch.no_grad():loaded=torch.cat([restored(b) for b in x.split(64)]).numpy();single=model(x[:1])[0]
    assert np.array_equal(loaded,actual) and torch.equal(model.predict_image(first),single)
    report=dict(plan_sha256=hashlib.sha256(p.read_bytes()).hexdigest(),artifact=str(path.relative_to(ROOT)).replace('\\','/'),artifact_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),artifact_bytes=path.stat().st_size,
        development_images=len(x),pixels_sha256=hashlib.sha256(pixels.tobytes()).hexdigest(),reference_prediction_sha256=hashlib.sha256(expected.tobytes()).hexdigest(),export_prediction_sha256=hashlib.sha256(actual.tobytes()).hexdigest(),
        max_normalized_delta=delta,roundtrip_exact=True,image_preprocess_exact=True,
        backbone_parameters=sum(p.numel() for p in model.parameters()),linear_coefficients=1539,normalization_values=1024,
        timing=timing(model,x[:1]),baseline_timing=timing(model.backbone,x[:1]),new_fits=0,optimizer_updates=0,hardware_writes=0,physical_movements=0,qualification_installed=False,
        limitations=['Selected unmasked control after reused-development diagnostic; export parity is not independent accuracy evidence',
        'Float32 backbone and float64 residual; CPU timing on this host only; no quantization or mobile latency claim',
        'No mask head, model fitting, physical calibration, coordinate uncertainty, or runtime installation'])
    out.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
if __name__=='__main__':run()
