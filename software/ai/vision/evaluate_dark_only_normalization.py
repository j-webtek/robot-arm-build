"""Frozen pixel-only brightness normalization; development diagnostic only."""
import hashlib,json,math,sys
from pathlib import Path
AI=Path(__file__).resolve().parents[1];ROOT=AI.parents[1]
sys.path[:0]=[str(AI),str(AI.parent/'src')]
import numpy as np
import torch
from PIL import Image,ImageEnhance
from vision.pose_model import KeyboardPoseNet
from vision.synthetic_keyboard import render,catalog_for_workspace,transform_target
from vision.train_pose import _pose_from_prediction
from vision.evaluate_pose_challenge import _alter


def normalize(image):
    pixels=np.asarray(image,dtype=np.float32)
    luminance=pixels@np.array([.299,.587,.114],dtype=np.float32)
    upper=float(np.percentile(luminance,95))
    if upper>=128:
        return image.copy(),1.0
    gain=float(np.clip(220/max(upper,1),1.0,2.5))
    result=Image.fromarray(np.clip(np.rint(pixels*gain),0,255).astype(np.uint8))
    return result,gain


def run():
    path=AI/'eval/dark_only_normalization_v0.manifest.json';m=json.loads(path.read_text())
    for f,h in m['file_sha256'].items():
        if hashlib.sha256((ROOT/f).read_bytes()).hexdigest()!=h:raise ValueError('frozen source changed')
    checkpoint=ROOT/m['checkpoint']
    if hashlib.sha256(checkpoint.read_bytes()).hexdigest()!=m['checkpoint_sha256']:raise ValueError('checkpoint changed')
    torch.set_num_threads(4);model=KeyboardPoseNet();model.load_state_dict(torch.load(checkpoint,map_location='cpu',weights_only=True));model.eval()
    catalog=catalog_for_workspace(ROOT)
    if catalog.content_sha256!=m['target_catalog_sha256']:raise ValueError('catalog changed')
    cases=[];digests={a:hashlib.sha256() for a in ('control','normalized')}
    for seed in range(m['seed_start'],m['seed_start']+m['seed_count']):
        for condition in m['conditions']:
            image,truth=render(seed,catalog,domain='appearance_shift' if condition=='appearance_shift' else 'standard')
            if condition=='challenge':image=_alter(image,seed)
            image=image.resize((128,96))
            if condition=='darkened_standard':image=ImageEnhance.Brightness(image).enhance(.5)
            fixed,gain=normalize(image)
            row=dict(seed=seed,condition=condition,gain=gain,arms={})
            actual=[transform_target(r.center.x,r.center.y,truth[:2],truth[2]) for r in catalog.keyboard_targets.values()]
            for arm,picture in [('control',image),('normalized',fixed)]:
                digests[arm].update(picture.tobytes())
                pixels=np.asarray(picture,dtype=np.uint8).transpose(2,0,1).copy()
                with torch.no_grad():pose=_pose_from_prediction(model(torch.from_numpy(pixels).unsqueeze(0).float()/255)[0])
                predicted=[transform_target(r.center.x,r.center.y,pose[:2],pose[2]) for r in catalog.keyboard_targets.values()]
                errors=[math.dist(a,b) for a,b in zip(actual,predicted)]
                row['arms'][arm]=dict(mean_mm=float(np.mean(errors)),maximum_mm=max(errors),center_mm=math.dist(pose[:2],truth[:2]),
                    yaw_degrees=abs(math.degrees(pose[2]-truth[2])),within_1mm_count=sum(e<=1 for e in errors))
            cases.append(row)
    summaries={};checks={}
    for condition in m['conditions']:
        summaries[condition]={}
        for arm in digests:
            rows=[c['arms'][arm] for c in cases if c['condition']==condition]
            summaries[condition][arm]=dict(images=len(rows),mean_mm=float(np.mean([r['mean_mm'] for r in rows])),
                above_3mm_images=sum(r['maximum_mm']>3 for r in rows),yaw_p95_degrees=float(np.percentile([r['yaw_degrees'] for r in rows],95)),
                within_1mm_fraction=sum(r['within_1mm_count'] for r in rows)/(len(rows)*len(catalog.keyboard_targets)))
        a=summaries[condition]['control'];b=summaries[condition]['normalized']
        checks[condition]=dict(mean_error=b['mean_mm']<a['mean_mm'] if condition=='darkened_standard' else b['mean_mm']<=1.05*a['mean_mm'],
            tail=b['above_3mm_images']<a['above_3mm_images'] if condition=='darkened_standard' else b['above_3mm_images']<=a['above_3mm_images'],
            yaw=b['yaw_p95_degrees']<=1.10*a['yaw_p95_degrees'])
    corrected_counts={c:sum(r['gain']!=1 for r in cases if r['condition']==c) for c in m['conditions']}
    report=dict(corrected_counts=corrected_counts,scope='DEVELOPMENT_ONLY',manifest_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
        image_data_sha256={a:d.hexdigest() for a,d in digests.items()},target_catalog_sha256=catalog.content_sha256,
        cases=cases,summaries=summaries,checks=checks,development_rule_passed=all(all(c.values()) for c in checks.values()),
        hardware_writes=0,physical_movements=0,qualification_installed=False,
        limitations=['Fixed correction only if image p95 luminance <128; threshold is an uncalibrated research parameter, selected after prior development diagnostics',
                    'Unchanged model was not trained with this normalization; distribution shift is possible',
                    'Reused development seeds and synthetic darkening; not real camera or held-out qualification',
                    'Cannot correct local shadows, occlusion or saturation; no runtime adoption'])
    (AI/'eval/dark_only_normalization_v0_scorecard.json').write_bytes((json.dumps(report,indent=2)+'\n').encode())
    print(json.dumps(dict(summaries=summaries,checks=checks,passed=report['development_rule_passed']),indent=2))


if __name__=='__main__':run()
