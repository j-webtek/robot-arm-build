"""Activation and output-bias audit of retained checkpoints; no updates."""
import hashlib,json,sys
from pathlib import Path
AI=Path(__file__).resolve().parents[1];ROOT=AI.parents[1];sys.path[:0]=[str(AI),str(AI.parent/'src')]
import numpy as np
import torch
from vision.mask_conditioned_pose import MaskConditionedPoseNet
from vision.landmark_occlusions import render_controlled
from vision.synthetic_keyboard import catalog_for_workspace
from vision.evaluate_dark_only_normalization import normalize


def summarize(pre, feature_output, bias):
    pre=np.asarray(pre,dtype=np.float64);feature_output=np.asarray(feature_output,dtype=np.float64);bias=np.asarray(bias,dtype=np.float64)
    if pre.ndim!=2 or len(pre)<2 or feature_output.shape!=(len(pre),3) or bias.shape!=(3,):raise ValueError('invalid array shape')
    if not all(np.isfinite(x).all() for x in (pre,feature_output,bias)):raise ValueError('nonfinite values')
    hidden=np.maximum(pre,0);positive=(pre>0).mean(axis=0);residual=feature_output+bias
    return dict(images=len(pre),hidden_units=pre.shape[1],positive_fraction=positive.tolist(),
        inactive_unit_ids=np.flatnonzero(positive==0).tolist(),always_positive_unit_ids=np.flatnonzero(positive==1).tolist(),
        hidden_std=hidden.std(axis=0).tolist(),preactivation_min=pre.min(axis=0).tolist(),preactivation_max=pre.max(axis=0).tolist(),
        all_hidden_zero_images=int((hidden==0).all(axis=1).sum()),output_bias_normalized=bias.tolist(),
        feature_output_mean_normalized=feature_output.mean(axis=0).tolist(),feature_output_std_normalized=feature_output.std(axis=0).tolist(),
        feature_output_rms_normalized=np.sqrt((feature_output**2).mean(axis=0)).tolist(),
        feature_output_exactly_zero=bool((feature_output==0).all()),residual_std_normalized=residual.std(axis=0).tolist())


def inspect(model,x):
    pres=[];parts=[]
    with torch.no_grad():
        for batch in x.split(64):
            features=model.backbone.features[:4](batch.float()/255);mask=model.segmentation(features).sigmoid()
            if model.mode=='constant':mask=torch.ones_like(mask)
            descriptor=model.descriptor(features,mask);pre=model.residual[0](descriptor);hidden=model.residual[1](pre)
            part=torch.nn.functional.linear(hidden,model.residual[2].weight,None)
            assert torch.equal(part+model.residual[2].bias,model.residual(descriptor))
            pres.append(pre);parts.append(part)
    pre=torch.cat(pres).numpy();part=torch.cat(parts).numpy()
    return dict(**summarize(pre,part,model.residual[2].bias.detach().numpy()),
        preactivation_sha256=hashlib.sha256(pre.tobytes()).hexdigest(),feature_output_sha256=hashlib.sha256(part.tobytes()).hexdigest())


def run():
    p=AI/'eval/residual_activations_v0_plan.json';plan=json.loads(p.read_text())
    for f,h in plan['file_sha256'].items():
        if hashlib.sha256((ROOT/f).read_bytes()).hexdigest()!=h:raise ValueError('source mismatch: '+f)
    out=AI/'eval/residual_activations_v0_report.json'
    if out.exists():raise FileExistsError(out)
    torch.set_num_threads(4);catalog=catalog_for_workspace(ROOT);pixels=[]
    start,count=plan['training_groups']
    for seed in range(start,start+count):
        for condition in plan['conditions']:
            image,_,_=render_controlled(seed,catalog,condition,'rectangle');image,_=normalize(image)
            pixels.append(np.asarray(image.resize((128,96))).transpose(2,0,1).copy())
    x=torch.from_numpy(np.stack(pixels));runs=[]
    pose=torch.load(ROOT/plan['checkpoint'],map_location='cpu',weights_only=True)
    for item in plan['models']:
        trained=MaskConditionedPoseNet.from_export(torch.load(ROOT/item['path'],map_location='cpu',weights_only=True))
        torch.manual_seed(item['seed']);initial=MaskConditionedPoseNet(item['mode']).eval()
        head=torch.load(ROOT/f"software/ai/results/segmentation_head_probe_{item['seed']}/head.pt",map_location='cpu',weights_only=True)
        initial.load_sources(pose,head)
        initial_hash=hashlib.sha256(b''.join(v.numpy().tobytes() for v in initial.state_dict().values())).hexdigest()
        previous=json.loads((AI/f"eval/pose_mask_residual_{item['seed']}_report.json").read_text())
        arm='control' if item['mode']=='constant' else 'occlusion'
        assert initial_hash==previous['results'][arm]['initial_state_sha256'] and trained.mode==initial.mode
        a=inspect(initial,x);b=inspect(trained,x)
        runs.append(dict(seed=item['seed'],mode=item['mode'],initial_state_sha256=initial_hash,initial=a,trained=b,
            newly_inactive_ids=sorted(set(b['inactive_unit_ids'])-set(a['inactive_unit_ids']))))
        print(item['seed'],item['mode'],'inactive',len(a['inactive_unit_ids']),'->',len(b['inactive_unit_ids']),'all-hidden-zero',b['all_hidden_zero_images'],'feature-std',b['feature_output_std_normalized'],flush=True)
    report=dict(plan_sha256=hashlib.sha256(p.read_bytes()).hexdigest(),training_pixels_sha256=hashlib.sha256(x.numpy().tobytes()).hexdigest(),runs=runs,
        optimizer_updates=0,hardware_writes=0,physical_movements=0,qualification_installed=False,
        limitations=['Initial and selected trained checkpoints only; no intermediate trajectory or causal optimizer attribution',
        'Inactive means nonpositive for every sampled training image, not every possible input',
        'Output components are normalized pose units; bias and feature energy are not additive because cross terms exist',
        'No retraining, activation modification, development fitting, physical calibration or runtime qualification'])
    out.write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
if __name__=='__main__':run()
