"""Development-only local-patch confidence comparison; no calibration/evaluation access."""
import hashlib,json,math,sys
from pathlib import Path
AI=Path(__file__).resolve().parents[1];ROOT=AI.parents[1]
sys.path[:0]=[str(AI),str(AI.parent/'src')]
import numpy as np
import torch
from torch import nn
from vision.pose_model import KeyboardPoseNet
from vision.synthetic_keyboard import render,catalog_for_workspace,transform_target
from vision.evaluate_pose_challenge import _alter
from vision.train_pose import _pose_from_prediction
from rocell_ai.confidence_metrics import score


def run():
    plan=json.loads((AI/'train/localization_confidence_v0_plan.json').read_text())
    arch=json.loads((AI/'train/local_features_dev_v0_plan.json').read_text())
    for path,digest in {**plan['file_sha256'],**arch['file_sha256']}.items():
        if hashlib.sha256((ROOT/path).read_bytes()).hexdigest()!=digest: raise ValueError('Frozen source changed: '+path)
    checkpoint=AI/'results/robust_pose_v0/pose_model.pt'
    if hashlib.sha256(checkpoint.read_bytes()).hexdigest()!=plan['checkpoint_sha256']: raise ValueError('checkpoint changed')
    output=AI/'results/local_features_dev_v0'
    output.mkdir(exist_ok=False)
    torch.set_num_threads(4);torch.manual_seed(arch['seed'])
    pose=KeyboardPoseNet();pose.load_state_dict(torch.load(checkpoint,map_location='cpu',weights_only=True));pose.eval()
    catalog=catalog_for_workspace(ROOT);keys=sorted(catalog.keyboard_targets)
    net=nn.Sequential(nn.Linear(194,32),nn.ReLU(),nn.Linear(32,1))
    data_hashes={}
    def samples(split):
        if split not in ('training','development'): raise ValueError('development study forbids held-out access')
        spec=plan['splits'][split];xs=[];ys=[];conditions=[];digest=hashlib.sha256()
        for seed in range(spec['seed_start'],spec['seed_start']+spec['seed_count']):
            for condition in plan['conditions']:
                image,truth=render(seed,catalog,domain='appearance_shift' if condition=='appearance_shift' else 'standard')
                if condition=='challenge': image=_alter(image,seed)
                pixels=np.asarray(image.resize((128,96)),dtype=np.uint8).transpose(2,0,1).copy()
                digest.update(pixels.tobytes())
                with torch.no_grad():
                    features=pose.features(torch.from_numpy(pixels).unsqueeze(0).float()/255)
                    predicted=_pose_from_prediction(pose.head(features)[0])
                for key in keys:
                    r=catalog.keyboard_targets[key]
                    estimated=transform_target(r.center.x,r.center.y,predicted[:2],predicted[2])
                    actual=transform_target(r.center.x,r.center.y,truth[:2],truth[2])
                    cx,cy=estimated[0]*256/610,estimated[1]*192/457
                    patch=image.convert('L').crop((round(cx)-8,round(cy)-8,round(cx)+8,round(cy)+8)).resize((8,8))
                    patch_features=torch.from_numpy(np.asarray(patch,dtype=np.float32).copy().flatten())/255
                    xs.append(torch.cat((features[0],torch.tensor([estimated[0]/610,estimated[1]/457]),patch_features)))
                    ys.append(math.dist(estimated,actual)<=plan['tolerance_mm']);conditions.append(condition)
        x=torch.stack(xs);y=torch.tensor(ys,dtype=torch.float32)
        digest.update(y.numpy().tobytes());data_hashes[split]=digest.hexdigest()
        print(split,len(y),flush=True)
        return x,y,conditions
    x,y,_=samples('training');dx,dy,_=samples('development')
    optimizer=torch.optim.Adam(net.parameters(),lr=arch['learning_rate'])
    loss_fn=nn.BCEWithLogitsLoss();best=float('inf');history=[]
    for epoch in range(arch['epochs']):
        net.train()
        for indexes in torch.randperm(len(y)).split(arch['batch_size']):
            optimizer.zero_grad();loss=loss_fn(net(x[indexes]).flatten(),y[indexes]);loss.backward();optimizer.step()
        net.eval()
        with torch.no_grad(): dev=float(loss_fn(net(dx).flatten(),dy))
        history.append(dev)
        if dev<best:
            best=dev;selected=epoch+1;torch.save(net.state_dict(),output/'model.pt')
    net.load_state_dict(torch.load(output/'model.pt',weights_only=True));net.eval()
    baseline=nn.Sequential(nn.Linear(130,32),nn.ReLU(),nn.Linear(32,1))
    baseline_path=AI/'results/localization_confidence_v0/model.pt'
    if hashlib.sha256(baseline_path.read_bytes()).hexdigest()!=arch['baseline_head_sha256']:
        raise ValueError('baseline confidence head changed')
    baseline.load_state_dict(torch.load(baseline_path,weights_only=True));baseline.eval()
    with torch.no_grad():
        candidate=torch.sigmoid(net(dx).flatten()).tolist()
        reference=torch.sigmoid(baseline(dx[:,:130]).flatten()).tolist()
    outcomes=[bool(v) for v in dy.tolist()]
    candidate_metrics=score(candidate,outcomes);reference_metrics=score(reference,outcomes)
    result=dict(scope='DEVELOPMENT_ONLY',selected_epoch=selected,development_bce=history,
        candidate=candidate_metrics,baseline=reference_metrics,
        brier_improvement=reference_metrics['brier_score']-candidate_metrics['brier_score'],
        parameter_count=sum(p.numel() for p in net.parameters()),data_sha256=data_hashes,
        model_sha256=hashlib.sha256((output/'model.pt').read_bytes()).hexdigest(),
        plan_sha256=hashlib.sha256((AI/'train/local_features_dev_v0_plan.json').read_bytes()).hexdigest(),
        hardware_writes=0,physical_movements=0,qualification_installed=False,
        limitations=['Development labels select epoch and assess feature choice; optimistic selection evidence only',
                    'No calibration or evaluation samples read; not an independent generalization result',
                    'Synthetic pixel projection only; local crop uses predicted center, never hidden truth',
                    'Known-target localization only; no runtime confidence or authority'])
    (AI/'eval/local_features_dev_v0_scorecard.json').write_bytes((json.dumps(result,indent=2)+'\n').encode())
    print(json.dumps({k:v for k,v in result.items() if k not in ('baseline','candidate','development_bce') }),flush=True)


if __name__=='__main__': run()
