"""Frozen-pose-feature localization correctness experiment, synthetic only."""
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
    arch=json.loads((AI/'train/localization_confidence_v0_architecture.json').read_text())
    for path,digest in {**plan['file_sha256'],**arch['file_sha256']}.items():
        if hashlib.sha256((ROOT/path).read_bytes()).hexdigest()!=digest: raise ValueError('Frozen source changed: '+path)
    checkpoint=AI/'results/robust_pose_v0/pose_model.pt'
    if hashlib.sha256(checkpoint.read_bytes()).hexdigest()!=plan['checkpoint_sha256']: raise ValueError('checkpoint changed')
    output=AI/'results/localization_confidence_v0'
    output.mkdir(exist_ok=False)
    torch.set_num_threads(4);torch.manual_seed(arch['seed'])
    pose=KeyboardPoseNet();pose.load_state_dict(torch.load(checkpoint,map_location='cpu',weights_only=True));pose.eval()
    catalog=catalog_for_workspace(ROOT);keys=sorted(catalog.keyboard_targets)
    net=nn.Sequential(nn.Linear(130,32),nn.ReLU(),nn.Linear(32,1))
    data_hashes={}
    def samples(split):
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
                    xs.append(torch.cat((features[0],torch.tensor([estimated[0]/610,estimated[1]/457]))))
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
    cx,cy,_=samples('calibration')
    with torch.no_grad(): logits=net(cx).flatten()
    temperatures=arch['temperature_candidates']
    losses=[float(loss_fn(logits/t,cy)) for t in temperatures]
    temperature=temperatures[min(range(len(losses)),key=losses.__getitem__)]
    # No evaluation labels are generated until model and temperature are selected.
    ex,ey,conditions=samples('evaluation')
    with torch.no_grad(): probabilities=torch.sigmoid(net(ex).flatten()/temperature).tolist()
    outcomes=[bool(v) for v in ey.tolist()]
    reports={'all':score(probabilities,outcomes,threshold=plan['threshold'],bins=plan['reliability_bins'])}
    for condition in plan['conditions']:
        indexes=[i for i,c in enumerate(conditions) if c==condition]
        reports[condition]=score([probabilities[i] for i in indexes],[outcomes[i] for i in indexes],threshold=plan['threshold'],bins=plan['reliability_bins'])
    criteria=plan['research_success_criteria']
    passed=all(r['acceptance_fraction']>=criteria['minimum_acceptance_fraction'] and
        r['false_accept_fraction_among_accepted'] is not None and r['false_accept_fraction_among_accepted']<=criteria['max_false_accept_fraction_among_accepted'] and
        r['brier_score']<=criteria['maximum_brier_score'] for r in reports.values())
    result=dict(status='SYNTHETIC_RESEARCH_PASS' if passed else 'SYNTHETIC_RESEARCH_FAILED',selected_epoch=selected,
        development_bce=history,temperature=temperature,calibration_bce=losses,metrics=reports,
        data_sha256=data_hashes,model_sha256=hashlib.sha256((output/'model.pt').read_bytes()).hexdigest(),
        parameter_count=sum(p.numel() for p in net.parameters()),target_ids=keys,
        plan_sha256=hashlib.sha256((AI/'train/localization_confidence_v0_plan.json').read_bytes()).hexdigest(),
        architecture_sha256=hashlib.sha256((AI/'train/localization_confidence_v0_architecture.json').read_bytes()).hexdigest(),
        hardware_writes=0,physical_movements=0,qualification_installed=False,
        limitations=['Synthetic known-target localization event only, not runtime observation confidence',
                    'Correlated target/view counts are descriptive; no population guarantee',
                    'No identity/visibility qualification, authenticated capture or physical measurements'])
    (AI/'eval/localization_confidence_v0_scorecard.json').write_bytes((json.dumps(result,indent=2)+'\n').encode())
    print(result['status'],json.dumps(reports['all']),flush=True)


if __name__=='__main__': run()
