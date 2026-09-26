"""Descriptive development-only tail stratification, not causal attribution."""
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
    path=AI/'eval/development_tails_v0.manifest.json';m=json.loads(path.read_text())
    for f,h in m['file_sha256'].items():
        if hashlib.sha256((ROOT/f).read_bytes()).hexdigest()!=h: raise ValueError('frozen source changed')
    checkpoint=ROOT/m['checkpoint']
    if hashlib.sha256(checkpoint.read_bytes()).hexdigest()!=m['checkpoint_sha256']: raise ValueError('checkpoint changed')
    torch.set_num_threads(4)
    model=KeyboardPoseNet();model.load_state_dict(torch.load(checkpoint,map_location='cpu',weights_only=True));model.eval()
    catalog=catalog_for_workspace(ROOT);cases=[];per_key={k:[] for k in catalog.keyboard_targets};digest=hashlib.sha256()
    for seed in range(m['seed_start'],m['seed_start']+m['seed_count']):
        for condition in m['conditions']:
            image,truth=render(seed,catalog,domain='appearance_shift' if condition=='appearance_shift' else 'standard')
            if condition=='challenge':image=_alter(image,seed)
            pixels=np.asarray(image.resize((128,96)),dtype=np.uint8).transpose(2,0,1).copy();digest.update(pixels.tobytes())
            with torch.no_grad(): pose=_pose_from_prediction(model(torch.from_numpy(pixels).unsqueeze(0).float()/255)[0])
            errors={}
            for key,r in catalog.keyboard_targets.items():
                a=transform_target(r.center.x,r.center.y,truth[:2],truth[2]);b=transform_target(r.center.x,r.center.y,pose[:2],pose[2])
                errors[key]=math.dist(a,b);per_key[key].append(errors[key])
            angle=math.degrees(truth[2]-math.pi)
            cases.append(dict(seed=seed,condition=condition,maximum_key_error_mm=max(errors.values()),
                worst_key=max(errors,key=errors.get),mean_key_error_mm=float(np.mean(list(errors.values()))),
                translation_mm=math.dist(pose[:2],truth[:2]),yaw_error_degrees=abs(math.degrees(pose[2]-truth[2])),
                position_bin=('left' if truth[0]<235 else 'right')+'_'+('front' if truth[1]<154 else 'rear'),
                orientation_bin='negative' if angle<-11/3 else ('positive' if angle>11/3 else 'central'),
                large_error=max(errors.values())>m['large_error_threshold_mm']))
    def summary(rows):
        return dict(images=len(rows),large_error_images=sum(r['large_error'] for r in rows),
            large_error_fraction=sum(r['large_error'] for r in rows)/len(rows),
            mean_maximum_key_error_mm=float(np.mean([r['maximum_key_error_mm'] for r in rows])),
            mean_translation_mm=float(np.mean([r['translation_mm'] for r in rows])),
            mean_yaw_error_degrees=float(np.mean([r['yaw_error_degrees'] for r in rows])))
    strata={field:{value:summary([r for r in cases if r[field]==value]) for value in sorted({r[field] for r in cases})}
            for field in ('condition','position_bin','orientation_bin')}
    report=dict(scope='DEVELOPMENT_ONLY',manifest_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
        image_data_sha256=digest.hexdigest(),target_catalog_sha256=catalog.content_sha256,
        all=summary(cases),strata=strata,
        per_key={k:dict(count=len(v),mean_mm=float(np.mean(v)),p95_mm=float(np.percentile(v,95)),
                       above_3mm_count=sum(e>m['large_error_threshold_mm'] for e in v)) for k,v in per_key.items()},
        cases=cases,hardware_writes=0,physical_movements=0,qualification_installed=False,
        limitations=['Truth-derived position/orientation bins are offline diagnostics, not runtime rejection rules',
                    'Marginal strata are correlated/confounded; not causal effects or significance estimates',
                    'No per-image occlusion labels; condition bundles do not isolate obstruction or lighting',
                    'Fixed >3mm diagnostic threshold, not a release criterion; no new held-out access'])
    (AI/'eval/development_tails_v0_scorecard.json').write_bytes((json.dumps(report,indent=2)+'\n').encode())
    print(json.dumps(dict(all=report['all'],strata=strata),indent=2))


if __name__=='__main__':run()
