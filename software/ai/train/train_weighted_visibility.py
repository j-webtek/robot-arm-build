"""Initial small landmark baseline; all metrics are synthetic development only."""
import hashlib,json,math,sys
from pathlib import Path
AI=Path(__file__).resolve().parents[1];ROOT=AI.parents[1]
sys.path[:0]=[str(AI),str(AI.parent/'src')]
import numpy as np
import torch
from vision.landmark_model import heatmap_coordinates
from vision.weighted_visibility_model import WeightedVisibilityNet
from vision.landmark_occlusions import render_controlled
from vision.synthetic_keyboard import catalog_for_workspace,transform_target
from vision.evaluate_dark_only_normalization import normalize
from vision.pose_model import KeyboardPoseNet
from vision.train_pose import _pose_from_prediction


def pose_from_corners(points):
    board=np.asarray(points)*np.array([610/256,457/192])
    center=board.mean(0);direction=board[1]-board[0]
    return float(center[0]),float(center[1]),math.atan2(direction[1],direction[0])


def balanced_visibility_loss(logits, visible):
    positive=-(visible*torch.nn.functional.logsigmoid(logits)).sum()/visible.sum().clamp_min(1)
    hidden=1-visible
    negative=-(hidden*torch.nn.functional.logsigmoid(-logits)).sum()/hidden.sum().clamp_min(1)
    return (positive+negative)/2


def run(mode):
    path=AI/'train/landmark_weighted_visibility_v0_plan.json';m=json.loads(path.read_text())
    for f,h in m['file_sha256'].items():
        if hashlib.sha256((ROOT/f).read_bytes()).hexdigest()!=h:raise ValueError('source changed')
    checkpoint=ROOT/m['baseline_checkpoint']
    if hashlib.sha256(checkpoint.read_bytes()).hexdigest()!=m['baseline_checkpoint_sha256']:raise ValueError('baseline changed')
    out=AI/'results'/('landmark_weighted_visibility_v0_'+mode)
    if out.exists():raise ValueError('preserve previous run')
    catalog=catalog_for_workspace(ROOT)
    if catalog.content_sha256!=m['target_catalog_sha256']:raise ValueError('catalog changed')
    torch.manual_seed(m['seed']);torch.set_num_threads(4)
    def dataset(split,style):
        pixels=[];points=[];visible=[];labels=[]
        start,count=m[split]
        for seed in range(start,start+count):
            for condition in m['conditions']:
                image,label,_=render_controlled(seed,catalog,condition,style);image,_=normalize(image)
                pixels.append(np.asarray(image,dtype=np.uint8).transpose(2,0,1).copy())
                points.append([[p['x_px'],p['y_px']] for p in label['landmarks']])
                visible.append([p['unoccluded_fraction'] for p in label['landmarks']]);labels.append(label)
        return torch.from_numpy(np.stack(pixels)),torch.tensor(points),torch.tensor(visible),labels
    x,y,v,_=dataset('training_groups','rectangle');dx,dy,dv,labels=dataset('development_groups','ellipse')
    device='cuda' if torch.cuda.is_available() else 'cpu';model=WeightedVisibilityNet(mode).to(device)
    optimizer=torch.optim.AdamW(model.parameters(),lr=m['learning_rate'])
    loader=torch.utils.data.DataLoader(torch.utils.data.TensorDataset(x,y,v),batch_size=32,shuffle=True,generator=torch.Generator().manual_seed(m['seed']))
    gx=torch.arange(64,device=device)[None,None,None,:];gy=torch.arange(48,device=device)[None,None,:,None]
    def loss(output,points,visible,corrected):
        # Gaussian soft labels on the stride4 grid; occluded corners excluded from localization loss.
        target=torch.exp(-((gx-points[:,:,0,None,None]/4)**2+(gy-points[:,:,1,None,None]/4)**2)/(2*1.5**2))
        target=target/target.sum((2,3),keepdim=True).clamp_min(1e-8)
        ce=-(target.flatten(2)*output['heatmap_logits'].flatten(2).log_softmax(-1)).sum(-1)
        loc=(ce*visible).sum()/visible.sum().clamp_min(1)
        vis=torch.nn.functional.binary_cross_entropy_with_logits(output['visibility_logits'],visible)
        if corrected=="control":return loc+vis
        coordinates=heatmap_coordinates(output['heatmap_logits'])
        error=((coordinates-points)/16).square().sum(-1)
        coordinate_loss=(error*visible).sum()/visible.sum().clamp_min(1)
        visibility_loss=balanced_visibility_loss(output['visibility_logits'],visible) if corrected in ('visibility_only','combined') else vis
        return loc+visibility_loss+(coordinate_loss if corrected in ('coordinate_only','combined') else 0)
    out.mkdir(parents=True);history=[];best=float('inf');selected=0
    for epoch in range(m['epochs']):
        model.train();total=0
        for bx,by,bv in loader:
            optimizer.zero_grad();value=loss(model(bx.to(device).float()/255),by.to(device),bv.to(device),"combined");value.backward();optimizer.step();total+=value.item()*len(bx)
        model.eval();dev_total=0
        with torch.no_grad():
            for start in range(0,len(dx),32):dev_total+=loss(model(dx[start:start+32].to(device).float()/255),dy[start:start+32].to(device),dv[start:start+32].to(device),"combined").item()*len(dx[start:start+32])
        score=dev_total/len(dx)
        if score<best:
            best=score;selected=epoch+1;torch.save({k:t.cpu() for k,t in model.state_dict().items()},out/'model.pt')
        history.append(dict(epoch=epoch+1,training_loss=total/len(x),development_loss=score));print(history[-1],flush=True)
    model.load_state_dict(torch.load(out/'model.pt',map_location=device,weights_only=True));model.eval()
    baseline=KeyboardPoseNet().to(device);baseline.load_state_dict(torch.load(checkpoint,map_location=device,weights_only=True));baseline.eval();cases=[]
    with torch.no_grad():
        for start in range(0,len(dx),32):
            batch=dx[start:start+32].to(device).float()/255;output=model(batch)
            coords=heatmap_coordinates(output['heatmap_logits']).cpu().numpy();vis=output['visibility_logits'].sigmoid().cpu().numpy()
            # Same normalized image, downsampled for existing128x96 pose baseline.
            from PIL import Image
            small=np.stack([np.asarray(Image.fromarray(a.numpy().transpose(1,2,0)).resize((128,96))).transpose(2,0,1).copy() for a in dx[start:start+32]])
            base=baseline(torch.from_numpy(small).to(device).float()/255).cpu()
            for j in range(len(coords)):
                label=labels[start+j];truth=label['pose'];row=dict(seed=label['seed'],condition=label['condition'],arms={})
                for name,pose in [('landmark',pose_from_corners(coords[j])),('baseline',_pose_from_prediction(base[j]))]:
                    errors=[math.dist(transform_target(t.center.x,t.center.y,pose[:2],pose[2]),transform_target(t.center.x,t.center.y,truth[:2],truth[2])) for t in catalog.keyboard_targets.values()]
                    row['arms'][name]=dict(mean_mm=float(np.mean(errors)),maximum_mm=max(errors),yaw_degrees=abs(math.degrees(math.atan2(math.sin(pose[2]-truth[2]),math.cos(pose[2]-truth[2])))))
                row.update(visibility_probabilities=vis[j].tolist(),visibility_targets=dv[start+j].tolist(),corner_error_px=np.linalg.norm(coords[j]-dy[start+j].numpy(),axis=1).tolist())
                cases.append(row)
    summaries={};checks={}
    for condition in m['conditions']:
        rows=[r for r in cases if r['condition']==condition];summaries[condition]={}
        for arm in ('baseline','landmark'):
            summaries[condition][arm]=dict(mean_mm=float(np.mean([r['arms'][arm]['mean_mm'] for r in rows])),tail=sum(r['arms'][arm]['maximum_mm']>3 for r in rows),yaw_p95=float(np.percentile([r['arms'][arm]['yaw_degrees'] for r in rows],95)))
        a,b=summaries[condition]['baseline'],summaries[condition]['landmark']
        checks[condition]=dict(mean=b['mean_mm']<=a['mean_mm']*1.05,tail=b['tail']<=a['tail'],yaw=b['yaw_p95']<=a['yaw_p95']*1.1)
    visibility=np.array([r['visibility_probabilities'] for r in cases]);truth_vis=dv.numpy()
    report=dict(scope='INITIAL_DEVELOPMENT_BASELINE',plan_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),history=history,selected_epoch=selected,
        checkpoint_sha256=hashlib.sha256((out/'model.pt').read_bytes()).hexdigest(),training_pixels_sha256=hashlib.sha256(x.numpy().tobytes()).hexdigest(),
        development_pixels_sha256=hashlib.sha256(dx.numpy().tobytes()).hexdigest(),training_images=len(x),development_images=len(dx),device=device,
        summaries=summaries,checks=checks,comparison_passed=all(all(v.values()) for v in checks.values()),cases=cases,
        fully_occluded_corners=int((truth_vis==0).sum()),false_visible_occluded=int(((truth_vis==0)&(visibility>=.5)).sum()),
        visibility_soft_target_mse=float(np.mean((visibility-truth_vis)**2)),hardware_writes=0,physical_movements=0,qualification_installed=False,
        limitations=['Reused training/development groups; ellipse occluder shape held out from rectangle training but not fresh evaluation',
                    'Unconditional four-corner pose decoding includes occluded predictions; diagnostic comparison only, no admission authority',
                    'Visibility outputs uncalibrated; synthetic geometry and inverse projection are not physical calibration',
                    'One seed, eight epochs; baseline uses pretrained weights, unequal training history; not architecture superiority evidence'])
    report['loss_mode']=mode
    report['clear_corners']=int((truth_vis==1).sum())
    report['true_visible_clear']=int(((truth_vis==1)&(visibility>=.5)).sum())
    (AI/'eval'/('landmark_weighted_visibility_v0_'+mode+'_scorecard.json')).write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(summaries=summaries,passed=report['comparison_passed'],false_visible=report['false_visible_occluded'],occluded=report['fully_occluded_corners']),indent=2))

    return report


if __name__=='__main__':
    results={name:run(name) for name in ('hard','weighted')}
    reference=results['hard']
    checks={}
    for name,candidate in results.items():
        by_condition={c:dict(mean=candidate['summaries'][c]['landmark']['mean_mm']<reference['summaries'][c]['landmark']['mean_mm'],
            tail=candidate['summaries'][c]['landmark']['tail']<=reference['summaries'][c]['landmark']['tail'],
            yaw=candidate['summaries'][c]['landmark']['yaw_p95']<=reference['summaries'][c]['landmark']['yaw_p95']*1.1) for c in reference['summaries']}
        visibility=candidate['false_visible_occluded']<reference['false_visible_occluded'] and candidate['true_visible_clear']/candidate['clear_corners']>=.9
        checks[name]=dict(conditions=by_condition,visibility_pass=visibility,passed=all(all(c.values()) for c in by_condition.values()) and visibility)
    report=dict(scope='MATCHED_HARD_WEIGHTED_VISIBILITY',checks=checks,
        report_hashes={name:hashlib.sha256((AI/f'eval/landmark_weighted_visibility_v0_{name}_scorecard.json').read_bytes()).hexdigest() for name in results},
        hardware_writes=0,physical_movements=0,qualification_installed=False,
        limitations=['Retrained matched hard/weighted heads; identical parameters and seed; GPU execution not bitwise guaranteed',
                    'One seed and reused development groups; no fresh generalization or architecture superiority claim',
                    'Passing a relative corrective rule would not establish replacement of pose baseline'])
    (AI/'eval/landmark_weighted_visibility_v0_comparison.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))
