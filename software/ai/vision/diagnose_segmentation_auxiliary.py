"""Frozen training-only gradient probe; zero optimizer steps."""
import hashlib,json,sys
from pathlib import Path
AI=Path(__file__).resolve().parents[1];ROOT=AI.parents[1];sys.path[:0]=[str(AI),str(AI.parent/'src')]
import numpy as np
import torch
from train.segmentation_auxiliary import SegmentationPoseNet,visible_case_target,balanced_mask_loss
from train.key_displacement_loss import key_loss
from vision.pose_model import KeyboardPoseNet
from vision.landmark_occlusions import render_controlled
from vision.synthetic_keyboard import catalog_for_workspace
from vision.evaluate_dark_only_normalization import normalize


def run():
    p=AI/'eval/segmentation_feasibility_v0_plan.json';plan=json.loads(p.read_text())
    for f,h in plan['file_sha256'].items():assert hashlib.sha256((ROOT/f).read_bytes()).hexdigest()==h
    out=AI/'eval/segmentation_feasibility_v0_report.json'
    if out.exists():raise FileExistsError(out)
    torch.manual_seed(plan['seed']);torch.set_num_threads(4);model=SegmentationPoseNet();state=torch.load(ROOT/plan['checkpoint'],weights_only=True,map_location='cpu');model.load_pose_weights(state);baseline=KeyboardPoseNet();baseline.load_state_dict(state);model.eval();baseline.eval()
    catalog=catalog_for_workspace(ROOT);offsets=torch.tensor([[t.center.x-242.5,t.center.y-158.5] for t in catalog.keyboard_targets.values()]);shared=list(model.backbone.features[:4].parameters());rows=[]
    def gradient(loss):return torch.cat([v.flatten() for v in torch.autograd.grad(loss,shared,retain_graph=True)])
    for start in plan['batch_starts']:
        pixels=[];labels=[];targets=[]
        for seed in range(start,start+8):
            for c in plan['conditions']:
                image,label,mask=render_controlled(seed,catalog,c,'rectangle');image,_=normalize(image);pose=label['pose']
                pixels.append(np.asarray(image.resize((128,96))).transpose(2,0,1).copy());labels.append([(pose[0]-235)/30,(pose[1]-154)/24,(pose[2]-np.pi)/.2]);targets.append(visible_case_target(label,mask))
        x=torch.from_numpy(np.stack(pixels)).float()/255;y=torch.tensor(labels,dtype=torch.float32);target=torch.stack(targets);prediction=model(x)
        with torch.no_grad():reference=baseline(x)
        assert torch.equal(prediction['pose'],reference)
        pose_loss=key_loss(prediction['pose'],y,offsets);mask_loss=balanced_mask_loss(prediction['mask_logits'],target);a,b=gradient(pose_loss),gradient(mask_loss)
        rows.append(dict(start=start,images=len(x),pixels_sha256=hashlib.sha256(np.stack(pixels).tobytes()).hexdigest(),targets_sha256=hashlib.sha256(target.numpy().tobytes()).hexdigest(),target_mean=float(target.mean()),empty_masks=int((target.flatten(1).sum(1)==0).sum()),pose_loss=float(pose_loss.detach()),mask_loss=float(mask_loss.detach()),pose_gradient_norm=float(a.norm()),mask_gradient_norm=float(b.norm()),weighted_gradient_ratio=float(plan['probe_coefficient']*b.norm()/a.norm()),gradient_cosine=float(torch.nn.functional.cosine_similarity(a,b,dim=0)),pose_max_delta=float((prediction['pose']-reference).abs().max().detach())))
    report=dict(plan_sha256=hashlib.sha256(p.read_bytes()).hexdigest(),rows=rows,extra_parameters=sum(p.numel() for p in model.segmentation.parameters()),optimizer_updates=0,hardware_writes=0,physical_movements=0,qualification_installed=False,limitations=['Synthetic visible-case geometry minus foreground,not perceptual segmentation truth','Four fixed training batches at initialization;gradient ratios do not predict training stability','No evaluation or qualification evidence;head may be discarded at inference'])
    out.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
if __name__=='__main__':run()
