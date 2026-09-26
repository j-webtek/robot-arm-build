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


def train(plan_path, output):
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
                pixels.append(np.asarray(image.resize((128,96)),dtype=np.uint8).transpose(2,0,1).copy())
                labels.append(((pose[0]-PHOTO_STUDY_CENTER_MM[0])/30,(pose[1]-PHOTO_STUDY_CENTER_MM[1])/24,(pose[2]-math.pi)/.2))
        return torch.from_numpy(np.stack(pixels)).float()/255,torch.tensor(labels,dtype=torch.float32)
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
            loss=torch.nn.functional.mse_loss(model(x.to(device)),y.to(device));loss.backward();optimizer.step()
            total+=float(loss.detach())*len(x)
        model.eval()
        with torch.no_grad():
            prediction=torch.cat([model(batch.to(device)).cpu() for batch in dev_x.split(64)])
            dev_loss=float(torch.nn.functional.mse_loss(prediction,dev_y))
        if dev_loss<best:
            best=dev_loss;selected=epoch+1
            torch.save({k:v.detach().cpu() for k,v in model.state_dict().items()},output/'pose_model.pt')
        history.append({'epoch':epoch+1,'training_mse':total/len(train_x),'development_mse':dev_loss})
        print(history[-1],flush=True)
    result={'schema':'rocell.ai_robust_pose_training.v0','plan_sha256':hashlib.sha256(plan_path.read_bytes()).hexdigest(),
        'selected_epoch':selected,'checkpoint_sha256':hashlib.sha256((output/'pose_model.pt').read_bytes()).hexdigest(),
        'selection':'minimum_development_mse_only','history':history,'device':device,'training_images':len(train_x),
        'development_images':len(dev_x),'calibration_or_evaluation_used_for_selection':False,
        'qualification_installed':False,'physical_execution_authorized':False}
    (output/'training_result.json').write_bytes((json.dumps(result,indent=2)+'\n').encode())
    return result

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--plan',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    args=p.parse_args();train(args.plan,args.output)
