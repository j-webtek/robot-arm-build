"""Fine-tune the frozen pose model on new challenge-augmented development groups."""
import hashlib,json,math,sys
from pathlib import Path
AI_DIR=Path(__file__).resolve().parents[1];ROOT=AI_DIR.parents[1]
sys.path[:0]=[str(AI_DIR),str(AI_DIR.parent/'src')]
import numpy as np
import torch
from vision.pose_model import KeyboardPoseNet
from vision.synthetic_keyboard import render,catalog_for_workspace,PHOTO_STUDY_CENTER_MM
from vision.evaluate_pose_challenge import _alter


def train(plan_path, output, size):
    if output.exists(): raise ValueError('Use a new output directory')
    plan=json.loads(plan_path.read_text())
    for relative,digest in plan['file_sha256'].items():
        if hashlib.sha256((ROOT/relative).read_bytes()).hexdigest()!=digest: raise ValueError('Frozen source changed')
    checkpoint=ROOT/plan['initial_checkpoint']
    if hashlib.sha256(checkpoint.read_bytes()).hexdigest()!=plan['initial_checkpoint_sha256']: raise ValueError('Initial checkpoint changed')
    torch.manual_seed(plan['training_seed']);torch.set_num_threads(4)
    catalog=catalog_for_workspace(ROOT)
    if catalog.content_sha256!=plan['target_catalog_sha256']: raise ValueError('Catalog changed')
    def samples(split):
        pixels=[];labels=[]
        start,count=plan[split]
        for seed in range(start,start+count):
            for condition in plan['conditions']:
                image,pose=render(seed,catalog,domain='appearance_shift' if condition=='appearance_shift' else 'standard')
                if condition=='challenge': image=_alter(image,seed)
                pixels.append(np.asarray(image.resize(tuple(size)),dtype=np.uint8).transpose(2,0,1).copy())
                labels.append(((pose[0]-PHOTO_STUDY_CENTER_MM[0])/30,(pose[1]-PHOTO_STUDY_CENTER_MM[1])/24,(pose[2]-math.pi)/.2))
        return torch.from_numpy(np.stack(pixels)),torch.tensor(labels,dtype=torch.float32)
    train_x,train_y=samples('training_groups');dev_x,dev_y=samples('development_groups')
    device='cuda' if torch.cuda.is_available() else 'cpu'
    model=KeyboardPoseNet().to(device);model.load_state_dict(torch.load(checkpoint,map_location=device,weights_only=True))
    optimizer=torch.optim.AdamW(model.parameters(),lr=plan['learning_rate'],weight_decay=.0001)
    loader=torch.utils.data.DataLoader(torch.utils.data.TensorDataset(train_x,train_y),batch_size=64,shuffle=True,
        generator=torch.Generator().manual_seed(plan['training_seed']))
    output.mkdir(parents=True)
    best=float('inf');history=[];selected=0
    for epoch in range(plan['epochs']):
        model.train();total=0
        for x,y in loader:
            optimizer.zero_grad(set_to_none=True)
            loss=torch.nn.functional.mse_loss(model(x.to(device).float()/255),y.to(device));loss.backward();optimizer.step()
            total+=float(loss.detach())*len(x)
        model.eval()
        with torch.no_grad():
            prediction=torch.cat([model(batch.to(device).float()/255).cpu() for batch in dev_x.split(64)])
            dev_loss=float(torch.nn.functional.mse_loss(prediction,dev_y))
        if dev_loss<best:
            best=dev_loss;selected=epoch+1
            torch.save({k:v.detach().cpu() for k,v in model.state_dict().items()},output/'pose_model.pt')
        history.append({'epoch':epoch+1,'training_mse':total/len(train_x),'development_mse':dev_loss})
        print(history[-1],flush=True)
    model.load_state_dict(torch.load(output/'pose_model.pt',map_location=device,weights_only=True));model.eval()
    with torch.no_grad():
        prediction=torch.cat([model(batch.to(device).float()/255).cpu() for batch in dev_x.split(64)])
    from vision.train_pose import _pose_from_prediction
    from vision.synthetic_keyboard import transform_target
    errors=[];group_max=[]
    for row,truth_row in zip(prediction,dev_y):
        predicted_pose=_pose_from_prediction(row);truth_pose=_pose_from_prediction(truth_row)
        local=[]
        for region in catalog.keyboard_targets.values():
            a=transform_target(region.center.x,region.center.y,predicted_pose[:2],predicted_pose[2])
            b=transform_target(region.center.x,region.center.y,truth_pose[:2],truth_pose[2])
            local.append(math.dist(a,b))
        errors.extend(local);group_max.append(max(local))
    result=dict(scope='DEVELOPMENT_ONLY',input_size=size,selected_epoch=selected,
        mean_mm=float(np.mean(errors)),p95_mm=float(np.percentile(errors,95)),maximum_mm=max(errors),
        within_1mm_fraction=sum(e<=1 for e in errors)/len(errors),target_view_count=len(errors),
        worst_image_error_p95_mm=float(np.percentile(group_max,95)),
        checkpoint_sha256=hashlib.sha256((output/'pose_model.pt').read_bytes()).hexdigest(),
        history=history,device=device,training_images=len(train_x),development_images=len(dev_x),
        training_pixels_sha256=hashlib.sha256(train_x.numpy().tobytes()).hexdigest(),
        development_pixels_sha256=hashlib.sha256(dev_x.numpy().tobytes()).hexdigest(),
        qualification_installed=False,hardware_writes=0,physical_movements=0)
    (output/'training_result.json').write_bytes((json.dumps(result,indent=2)+'\n').encode())
    return result


if __name__=='__main__':
    plan_path=AI_DIR/'train/matched_resolution_v0_plan.json'
    plan=json.loads(plan_path.read_text())
    results=[]
    for size in plan['sizes']:
        results.append(train(plan_path,AI_DIR/'results'/('matched_resolution_v0_'+str(size[0])),size))
    report=dict(scope='DEVELOPMENT_ONLY',plan_sha256=hashlib.sha256(plan_path.read_bytes()).hexdigest(),
        results=results,hardware_writes=0,physical_movements=0,qualification_installed=False,
        limitations=['Same pretrained checkpoint originated at 128x96; this is equal-budget fine-tuning, not training from scratch',
                    'Epoch selected on development MSE; development metrics are optimistic selection evidence',
                    'Renderer remains 256x192; no real camera or held-out evaluation data',
                    'One training seed per resolution; no claim of statistical significance'])
    (AI_DIR/'eval/matched_resolution_v0_scorecard.json').write_bytes((json.dumps(report,indent=2)+'\n').encode())
    print([(r['input_size'],r['mean_mm'],r['within_1mm_fraction']) for r in results],flush=True)
