"""Head-only learning probe; immutable pose model, no localization promotion."""
import hashlib,json,math,sys
from pathlib import Path
AI=Path(__file__).resolve().parents[1];ROOT=AI.parents[1];sys.path[:0]=[str(AI),str(AI.parent/'src')]
import numpy as np
import torch
from train.segmentation_auxiliary import SegmentationPoseNet,visible_case_target,balanced_mask_loss
from vision.landmark_occlusions import render_controlled
from vision.synthetic_keyboard import catalog_for_workspace
from vision.evaluate_dark_only_normalization import normalize


def state_hash(model):
    return hashlib.sha256(b''.join(v.detach().cpu().numpy().tobytes() for v in model.state_dict().values())).hexdigest()


def metrics(logits,target):
    predicted=logits.sigmoid()>=.5;actual=target>=.5
    intersection=(predicted&actual).flatten(1).sum(1);union=(predicted|actual).flatten(1).sum(1)
    return dict(balanced_bce=float(balanced_mask_loss(logits,target)),mean_iou=float((intersection/union.clamp_min(1)).float().mean()))


def run():
    p=AI/'train/segmentation_head_probe_v0_plan.json';plan=json.loads(p.read_text())
    for f,h in plan['file_sha256'].items():assert hashlib.sha256((ROOT/f).read_bytes()).hexdigest()==h
    output=AI/'eval/segmentation_head_probe_v0_report.json'
    if output.exists():raise FileExistsError(output)
    for seed in plan['seeds']:
        if (AI/f'results/segmentation_head_probe_{seed}').exists():raise FileExistsError(seed)
    torch.set_num_threads(4);device='cuda' if torch.cuda.is_available() else 'cpu';catalog=catalog_for_workspace(ROOT)
    state=torch.load(ROOT/plan['checkpoint'],map_location=device,weights_only=True)
    feature_model=SegmentationPoseNet().to(device).eval();feature_model.load_pose_weights(state)
    for param in feature_model.backbone.parameters():param.requires_grad_(False)
    def samples(start,count,style):
        pixels=[];targets=[]
        for seed in range(start,start+count):
            for c in plan['conditions']:
                image,label,mask=render_controlled(seed,catalog,c,style);image,_=normalize(image)
                pixels.append(np.asarray(image.resize((128,96))).transpose(2,0,1).copy());targets.append(visible_case_target(label,mask))
        pixels=torch.from_numpy(np.stack(pixels));features=[];poses=[]
        with torch.no_grad():
            for batch in pixels.split(64):
                x=batch.to(device).float()/255;features.append(feature_model.backbone.features[:4](x).cpu());poses.append(feature_model.backbone(x).cpu())
        return pixels,torch.cat(features),torch.stack(targets),torch.cat(poses)
    tx,tf,tt,_=samples(*plan['training_groups'],'rectangle');dx,df,dt,reference=samples(*plan['development_groups'],'ellipse');runs=[]
    for seed in plan['seeds']:
        torch.manual_seed(seed);model=SegmentationPoseNet().to(device).eval();model.load_pose_weights(state)
        for param in model.backbone.parameters():param.requires_grad_(False)
        before=state_hash(model.backbone)
        def evaluate(features,target):
            with torch.no_grad():logits=torch.cat([model.segmentation(f.to(device)).cpu() for f in features.split(64)])
            return metrics(logits,target),{c:metrics(logits[i::4],target[i::4]) for i,c in enumerate(plan['conditions'])}
        initial,_=evaluate(df,dt)
        loader=torch.utils.data.DataLoader(torch.utils.data.TensorDataset(tf,tt),batch_size=64,shuffle=True,generator=torch.Generator().manual_seed(seed))
        optimizer=torch.optim.AdamW(model.segmentation.parameters(),lr=plan['learning_rate'],weight_decay=.0001);history=[]
        for epoch in range(plan['epochs']):
            total=0.
            for f,target in loader:
                optimizer.zero_grad(set_to_none=True);loss=balanced_mask_loss(model.segmentation(f.to(device)),target.to(device));loss.backward();optimizer.step();total+=float(loss.detach())*len(f)
            score,_=evaluate(df,dt);history.append(dict(epoch=epoch+1,train_bce=total/len(tf),**score));print(seed,history[-1],flush=True)
        final,conditions=evaluate(df,dt);train_final,_=evaluate(tf,tt)
        with torch.no_grad():poses=torch.cat([model.backbone(x.to(device).float()/255).cpu() for x in dx.split(64)])
        assert state_hash(model.backbone)==before and torch.equal(poses,reference)
        directory=AI/f'results/segmentation_head_probe_{seed}';directory.mkdir();torch.save(model.segmentation.cpu().state_dict(),directory/'head.pt')
        runs.append(dict(seed=seed,initial=initial,final=final,train_final=train_final,conditions=conditions,history=history,backbone_before_sha256=before,backbone_after_sha256=state_hash(model.backbone),pose_max_delta=float((poses-reference).abs().max()),head_sha256=hashlib.sha256((directory/'head.pt').read_bytes()).hexdigest(),passed=all(m['mean_iou']>=plan['minimum_iou'] for m in conditions.values()) and final['balanced_bce']<initial['balanced_bce']))
    report=dict(plan_sha256=hashlib.sha256(p.read_bytes()).hexdigest(),runs=runs,device=device,training_pixels_sha256=hashlib.sha256(tx.numpy().tobytes()).hexdigest(),development_pixels_sha256=hashlib.sha256(dx.numpy().tobytes()).hexdigest(),training_targets_sha256=hashlib.sha256(tt.numpy().tobytes()).hexdigest(),development_targets_sha256=hashlib.sha256(dt.numpy().tobytes()).hexdigest(),head_updates_per_seed=plan['epochs']*len(loader),pose_updates=0,hardware_writes=0,physical_movements=0,qualification_installed=False,limitations=['Fixed8epochs and0.5mask threshold;minimum per-condition IoU0.8 is a research feasibility criterion,not qualification','Reused synthetic development;geometric visible-case labels,not perceptual/physical truth','No localization accuracy change is possible with frozen pose weights'])
    output.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps([{k:r[k] for k in ['seed','initial','final','train_final','passed','pose_max_delta']} for r in runs],indent=2))
if __name__=='__main__':run()
