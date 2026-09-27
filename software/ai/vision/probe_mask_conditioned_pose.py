"""Architecture feasibility only: no fitting, no accuracy improvement claim."""
import hashlib,json,sys,time,statistics
from io import BytesIO
from pathlib import Path
AI=Path(__file__).resolve().parents[1];ROOT=AI.parents[1];sys.path[:0]=[str(AI),str(AI.parent/'src')]
import numpy as np
import torch
from vision.mask_conditioned_pose import MaskConditionedPoseNet
from vision.pose_model import KeyboardPoseNet
from vision.landmark_occlusions import render_controlled
from vision.synthetic_keyboard import catalog_for_workspace
from vision.evaluate_dark_only_normalization import normalize


def timing(model, image):
    with torch.no_grad():
        for _ in range(10):model(image)
        times=[]
        for _ in range(100):
            start=time.perf_counter_ns();model(image);times.append((time.perf_counter_ns()-start)/1e6)
    return dict(median_ms=statistics.median(times),p95_ms=float(np.percentile(times,95)),iterations=100,warmup=10,batch_size=len(image))


def run():
    p=AI/'eval/mask_conditioned_probe_v0_plan.json';plan=json.loads(p.read_text())
    for f,h in plan['file_sha256'].items():
        if hashlib.sha256((ROOT/f).read_bytes()).hexdigest()!=h:raise ValueError('frozen artifact changed: '+f)
    out=AI/'eval/mask_conditioned_probe_v0_report.json'
    if out.exists():raise FileExistsError(out)
    torch.set_num_threads(4);torch.manual_seed(260926)
    catalog=catalog_for_workspace(ROOT);pixels=[]
    for seed in range(*plan['scene_range']):
        for condition in plan['conditions']:
            image,_,_=render_controlled(seed,catalog,condition,'rectangle');image,_=normalize(image)
            pixels.append(np.asarray(image.resize((128,96))).transpose(2,0,1).copy())
    pixels=np.stack(pixels);x=torch.from_numpy(pixels).float()/255
    pose=torch.load(ROOT/plan['checkpoint'],map_location='cpu',weights_only=True)
    baseline=KeyboardPoseNet().eval();baseline.load_state_dict(pose)
    with torch.no_grad():reference=baseline(x)
    results=[]
    for seed,head in zip(plan['seeds'],plan['heads']):
        mask=torch.load(ROOT/head,map_location='cpu',weights_only=True)
        models=[]
        for mode in ['constant','predicted']:
            torch.manual_seed(seed);model=MaskConditionedPoseNet(mode).eval();model.load_sources(pose,mask);models.append(model)
            with torch.no_grad():prediction=model(x)
            assert torch.equal(prediction,reference)
            stream=BytesIO();torch.save(model.export(),stream);size=stream.tell();stream.seek(0)
            restored=MaskConditionedPoseNet.from_export(torch.load(stream,weights_only=True))
            with torch.no_grad():assert torch.equal(restored(x),prediction)
            # A deterministic nonzero residual is a wiring check, not learned behavior.
            with torch.no_grad():model.residual[-1].weight.fill_(.01)
            with torch.no_grad():nonzero=model(x)
            model.zero_grad(set_to_none=True);model(x).square().mean().backward()
            assert all(p.grad is None for p in model.backbone.parameters())
            assert all(p.grad is None for p in model.segmentation.parameters())
            assert all(p.grad is not None and torch.isfinite(p.grad).all() for p in model.residual.parameters())
            artifact=model.export();reloaded=MaskConditionedPoseNet.from_export(artifact)
            with torch.no_grad():assert torch.equal(reloaded(x),nonzero)
            results.append(dict(seed=seed,mode=mode,parameters=sum(p.numel() for p in model.parameters()),
                trainable_parameters=sum(p.numel() for p in model.parameters() if p.requires_grad),
                artifact_bytes=size,initial_max_pose_delta=float((prediction-reference).abs().max()),
                nonzero_residual_max_delta=float((nonzero-reference).abs().max()),roundtrip_exact=True,
                frozen_gradients_absent=True,residual_gradients_finite=True,timing=timing(model,x[:1])))
        assert all(torch.equal(a,b) for a,b in zip(models[0].state_dict().values(),models[1].state_dict().values()))
        with torch.no_grad():delta=float((models[0](x)-models[1](x)).abs().max())
        assert delta>0
        for r in results[-2:]:r['nonzero_mask_conditioning_delta']=delta
    report=dict(plan_sha256=hashlib.sha256(p.read_bytes()).hexdigest(),input_pixels_sha256=hashlib.sha256(pixels.tobytes()).hexdigest(),
        images=len(x),baseline_parameters=sum(p.numel() for p in baseline.parameters()),baseline_timing=timing(baseline,x[:1]),
        runs=results,optimizer_updates=0,hardware_writes=0,physical_movements=0,qualification_installed=False,
        limitations=['CPU timings are descriptive for this host, not deployment latency guarantees',
        'Backpropagation and manually assigned nonzero weights check wiring only; no model fitting or accuracy improvement',
        'Both arms retain baseline and learned segmentation head; head pretraining cost304 updates per seed is inherited',
        'No runtime calibration, uncertainty qualification, physical images, or new holdout'])
    out.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
if __name__=='__main__':run()
