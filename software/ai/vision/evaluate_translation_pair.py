"""Frozen fresh paired evaluation; no calibration, training or qualification."""
import hashlib,json,math,sys
from pathlib import Path
AI=Path(__file__).resolve().parents[1];ROOT=AI.parents[1]
sys.path[:0]=[str(AI),str(AI.parent/'src')]
import numpy as np
import torch
from vision.pose_model import KeyboardPoseNet
from vision.synthetic_keyboard import render,catalog_for_workspace,transform_target
from vision.train_pose import _pose_from_prediction
from vision.evaluate_pose_challenge import _alter


def run():
    path=AI/'eval/translation_pair_v0.manifest.json';m=json.loads(path.read_text())
    for f,h in m['file_sha256'].items():
        if hashlib.sha256((ROOT/f).read_bytes()).hexdigest()!=h: raise ValueError('frozen source changed')
    torch.set_num_threads(4);models={}
    for name,spec in m['models'].items():
        checkpoint=ROOT/spec['path']
        if hashlib.sha256(checkpoint.read_bytes()).hexdigest()!=spec['sha256']: raise ValueError('checkpoint changed')
        model=KeyboardPoseNet();model.load_state_dict(torch.load(checkpoint,map_location='cpu',weights_only=True));model.eval();models[name]=model
    catalog=catalog_for_workspace(ROOT)
    if catalog.content_sha256!=m['target_catalog_sha256']: raise ValueError('catalog changed')
    data={name:{c:dict(errors=[],centers=[],yaw=[]) for c in m['conditions']} for name in models}
    groups=[];digest=hashlib.sha256()
    for seed in range(m['seed_start'],m['seed_start']+m['seed_count']):
        group=dict(seed=seed,models={name:[] for name in models})
        for condition in m['conditions']:
            image,truth=render(seed,catalog,domain='appearance_shift' if condition=='appearance_shift' else 'standard')
            if condition=='challenge': image=_alter(image,seed)
            pixels=np.asarray(image.resize((128,96)),dtype=np.uint8).transpose(2,0,1).copy();digest.update(pixels.tobytes())
            actual=[transform_target(r.center.x,r.center.y,truth[:2],truth[2]) for r in catalog.keyboard_targets.values()]
            for name,model in models.items():
                with torch.no_grad(): pose=_pose_from_prediction(model(torch.from_numpy(pixels).unsqueeze(0).float()/255)[0])
                predicted=[transform_target(r.center.x,r.center.y,pose[:2],pose[2]) for r in catalog.keyboard_targets.values()]
                errors=[math.dist(a,b) for a,b in zip(actual,predicted)]
                d=data[name][condition];d['errors'].extend(errors);d['centers'].append(math.dist(pose[:2],truth[:2]));d['yaw'].append(abs(math.degrees(pose[2]-truth[2])))
                group['models'][name].append(dict(condition=condition,mean_mm=float(np.mean(errors)),maximum_mm=max(errors)))
        groups.append(group)
    def summarize(d):
        e=d['errors']
        return dict(count=len(e),mean_mm=float(np.mean(e)),p95_mm=float(np.percentile(e,95)),maximum_mm=max(e),
            within_1mm_fraction=sum(v<=1 for v in e)/len(e),center_mean_mm=float(np.mean(d['centers'])),yaw_p95_degrees=float(np.percentile(d['yaw'],95)))
    reports={}
    for name,conditions in data.items():
        reports[name]={c:summarize(d) for c,d in conditions.items()}
        reports[name]['all']=summarize({k:[v for d in conditions.values() for v in d[k]] for k in ('errors','centers','yaw')})
    decisions={}
    for c in ['all',*m['conditions']]:
        a,b=reports['control'][c],reports['candidate'][c]
        decisions[c]=dict(mean_key_improves=b['mean_mm']<a['mean_mm'],center_improves=b['center_mean_mm']<a['center_mean_mm'],
            within_1mm_not_worse=b['within_1mm_fraction']>=a['within_1mm_fraction'],yaw_guard=b['yaw_p95_degrees']<=m['maximum_yaw_p95_ratio']*a['yaw_p95_degrees'])
    passed=all(all(v.values()) for v in decisions.values())
    report=dict(status='PAIRED_RESEARCH_CRITERIA_PASS' if passed else 'PAIRED_RESEARCH_CRITERIA_FAIL',
        manifest_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),image_data_sha256=digest.hexdigest(),
        metrics=reports,criteria=decisions,groups=groups,hardware_writes=0,physical_movements=0,qualification_installed=False,
        limitations=['Synthetic known-target geometry only; no confidence/visibility or physical validation',
                    'Correlated key/view counts; descriptive comparison, not statistical significance',
                    'No calibrated uncertainty, runtime checkpoint replacement or qualification'])
    (AI/'eval/translation_pair_v0_scorecard.json').write_bytes((json.dumps(report,indent=2)+'\n').encode())
    print(report['status']);print(json.dumps(reports,indent=2));print(json.dumps(decisions))


if __name__=='__main__': run()
