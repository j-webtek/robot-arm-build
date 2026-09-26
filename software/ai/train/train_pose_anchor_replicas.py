"""Paired synthetic pose fine-tuning; no runtime or physical authority."""
import hashlib,json,math,sys
from pathlib import Path
AI=Path(__file__).resolve().parents[1];ROOT=AI.parents[1];sys.path[:0]=[str(AI),str(AI.parent/'src')]
import numpy as np
import torch
from vision.pose_model import KeyboardPoseNet
from vision.train_pose import _pose_from_prediction
from vision.landmark_occlusions import render_controlled
from vision.synthetic_keyboard import catalog_for_workspace
from vision.evaluate_dark_only_normalization import normalize
from vision.diagnose_pose_tail import decompose
from train.key_displacement_loss import key_loss


def anchor_loss(prediction,teacher,mask,offsets):
    if not bool(mask.any()):return prediction.sum()*0
    return key_loss(prediction[mask],teacher[mask].detach(),offsets)


def conditions(arm):
    return ['standard','appearance_shift','partial','full']


def run(seed):
    prefix=f"pose_anchor_replica_{seed}"
    p=AI/'train'/f'{prefix}_plan.json';plan=json.loads(p.read_text())
    for f,h in plan['file_sha256'].items():assert hashlib.sha256((ROOT/f).read_bytes()).hexdigest()==h
    output=AI/'eval'/f'{prefix}_report.json'
    if output.exists():raise FileExistsError(output)
    for arm in ['control','occlusion']:
        if (AI/'results'/(prefix+'_'+arm)).exists():raise FileExistsError(arm)
    torch.set_num_threads(4);catalog=catalog_for_workspace(ROOT);device='cuda' if torch.cuda.is_available() else 'cpu'
    def samples(start,count,conds,style):
        pixels=[];labels=[];metadata=[]
        for seed in range(start,start+count):
            for c in conds:
                image,label,_=render_controlled(seed,catalog,c,style);image,_=normalize(image);pose=label['pose']
                pixels.append(np.asarray(image.resize((128,96))).transpose(2,0,1).copy())
                labels.append([(pose[0]-235)/30,(pose[1]-154)/24,(pose[2]-math.pi)/.2]);metadata.append((seed,c,pose))
        return torch.from_numpy(np.stack(pixels)),torch.tensor(labels,dtype=torch.float32),metadata
    dx,dy,metadata=samples(*plan['development_groups'],plan['conditions'],'ellipse')
    results={}
    offsets=torch.tensor([[t.center.x-242.5,t.center.y-158.5] for t in catalog.keyboard_targets.values()],device=device)
    def score(model):
        model.eval()
        with torch.no_grad():pred=torch.cat([model(x.to(device).float()/255).cpu() for x in dx.split(64)])
        rows=[dict(seed=seed,condition=c,**decompose(_pose_from_prediction(row),truth,catalog.keyboard_targets.values())) for row,(seed,c,truth) in zip(pred,metadata)]
        summaries={}
        for c in plan['conditions']:
            cases=[r for r in rows if r['condition']==c]
            summaries[c]=dict(mean_mm=float(np.mean([r['mean_mm'] for r in cases])),tail=sum(r['maximum_mm']>3 for r in cases),yaw_p95=float(np.percentile([r['yaw_degrees'] for r in cases],95)))
        return rows,summaries
    model=KeyboardPoseNet().to(device);model.load_state_dict(torch.load(ROOT/plan['checkpoint'],map_location=device,weights_only=True));rows,summary=score(model);results['baseline']=dict(rows=rows,summaries=summary)
    teacher=model;teacher.eval()
    for parameter in teacher.parameters():parameter.requires_grad_(False)
    for arm in ['control','occlusion']:
        torch.manual_seed(plan['seed']);model=KeyboardPoseNet().to(device);model.load_state_dict(torch.load(ROOT/plan['checkpoint'],map_location=device,weights_only=True))
        tx,ty,training_metadata=samples(*plan['training_groups'],conditions(arm),'rectangle')
        with torch.no_grad():teacher_y=torch.cat([teacher(x.to(device).float()/255).cpu() for x in tx.split(64)])
        clear_mask=torch.tensor([c in ('standard','appearance_shift') for _,c,_ in training_metadata])
        loader=torch.utils.data.DataLoader(torch.utils.data.TensorDataset(tx,ty,teacher_y,clear_mask),batch_size=64,shuffle=True,generator=torch.Generator().manual_seed(plan['seed']))
        optimizer=torch.optim.AdamW(model.parameters(),lr=plan['learning_rate'],weight_decay=.0001);history=[];best=float('inf');directory=AI/'results'/(prefix+'_'+arm);directory.mkdir()
        for epoch in range(plan['epochs']):
            model.train();total=0.
            for x,y,teacher_batch,mask in loader:
                optimizer.zero_grad(set_to_none=True);prediction=model(x.to(device).float()/255);truth=y.to(device);res=prediction-truth
                loss=key_loss(prediction,truth,offsets)
                if arm!='control':loss=loss+plan['anchor_coefficient']*anchor_loss(prediction,teacher_batch.to(device),mask.to(device),offsets)
                loss.backward();optimizer.step();total+=float(loss.detach())*len(x)
            model.eval()
            with torch.no_grad():pred=torch.cat([model(x.to(device).float()/255).cpu() for x in dx.split(64)])
            dev=float((pred-dy).square().mean());history.append(dict(epoch=epoch+1,training_loss=total/len(tx),development_mse=dev))
            if dev<best:best=dev;selected=epoch+1;torch.save({k:v.detach().cpu() for k,v in model.state_dict().items()},directory/'pose_model.pt')
            print(arm,history[-1],flush=True)
        model.load_state_dict(torch.load(directory/'pose_model.pt',map_location=device,weights_only=True));rows,summary=score(model)
        results[arm]=dict(rows=rows,summaries=summary,history=history,selected_epoch=selected,training_images=len(tx),anchor_images=int(clear_mask.sum()),teacher_predictions_sha256=hashlib.sha256(teacher_y.numpy().tobytes()).hexdigest(),training_pixels_sha256=hashlib.sha256(tx.numpy().tobytes()).hexdigest(),checkpoint_sha256=hashlib.sha256((directory/'pose_model.pt').read_bytes()).hexdigest())
    checks={}
    for reference in ['baseline','control']:
        checks[reference]={}
        for c in plan['conditions']:
            a=results[reference]['summaries'][c];b=results['occlusion']['summaries'][c]
            checks[reference][c]=dict(mean=b['mean_mm']<=a['mean_mm'],tail=b['tail']<=a['tail'],yaw=b['yaw_p95']<=1.1*a['yaw_p95'])
        checks[reference]['occlusion_tail_improves']=sum(results['occlusion']['summaries'][c]['tail'] for c in ['partial','full'])<sum(results[reference]['summaries'][c]['tail'] for c in ['partial','full'])
    passed=all(all(all(v.values()) if isinstance(v,dict) else v for v in ref.values()) for ref in checks.values())
    report=dict(plan_sha256=hashlib.sha256(p.read_bytes()).hexdigest(),results=results,checks=checks,passed=passed,device=device,development_pixels_sha256=hashlib.sha256(dx.numpy().tobytes()).hexdigest(),hardware_writes=0,physical_movements=0,qualification_installed=False,limitations=['One training seed; GPU nondeterminism','Reused synthetic development selects epoch and evaluates candidate; not holdout qualification','Rectangle training versus ellipse development; no physical camera data or calibrated uncertainty'])
    output.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(dict(summaries={a:r['summaries'] for a,r in results.items()},checks=checks,passed=passed),indent=2))
if __name__=='__main__':
    for seed in (260927,260928):run(seed)
