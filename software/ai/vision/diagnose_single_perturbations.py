"""Paired added perturbations on existing development renders; not physical claims."""
import hashlib,json,math,sys
from pathlib import Path
AI=Path(__file__).resolve().parents[1];ROOT=AI.parents[1]
sys.path[:0]=[str(AI),str(AI.parent/'src')]
import numpy as np
import torch
from PIL import ImageEnhance,ImageFilter,ImageDraw
from vision.pose_model import KeyboardPoseNet
from vision.synthetic_keyboard import render,catalog_for_workspace,transform_target
from vision.train_pose import _pose_from_prediction


def perturb(image,condition):
    if condition=='base': return image.copy()
    if condition=='darken': return ImageEnhance.Brightness(image).enhance(0.5)
    if condition=='blur': return image.filter(ImageFilter.GaussianBlur(1.2))
    if condition=='obstruction':
        result=image.copy();ImageDraw.Draw(result).rectangle((96,40,103,90),fill=(17,20,24));return result
    raise ValueError('unknown perturbation')


def run():
    path=AI/'eval/single_perturbations_v0.manifest.json';m=json.loads(path.read_text())
    for f,h in m['file_sha256'].items():
        if hashlib.sha256((ROOT/f).read_bytes()).hexdigest()!=h:raise ValueError('frozen source changed')
    checkpoint=ROOT/m['checkpoint']
    if hashlib.sha256(checkpoint.read_bytes()).hexdigest()!=m['checkpoint_sha256']:raise ValueError('checkpoint changed')
    torch.set_num_threads(4);model=KeyboardPoseNet();model.load_state_dict(torch.load(checkpoint,map_location='cpu',weights_only=True));model.eval()
    catalog=catalog_for_workspace(ROOT);cases=[];digests={c:hashlib.sha256() for c in m['conditions']}
    for seed in range(m['seed_start'],m['seed_start']+m['seed_count']):
        base,truth=render(seed,catalog,domain='standard');row=dict(seed=seed,conditions={})
        actual=[transform_target(r.center.x,r.center.y,truth[:2],truth[2]) for r in catalog.keyboard_targets.values()]
        for condition in m['conditions']:
            image=perturb(base,condition);digests[condition].update(image.tobytes())
            pixels=np.asarray(image.resize((128,96)),dtype=np.uint8).transpose(2,0,1).copy()
            with torch.no_grad():pose=_pose_from_prediction(model(torch.from_numpy(pixels).unsqueeze(0).float()/255)[0])
            predicted=[transform_target(r.center.x,r.center.y,pose[:2],pose[2]) for r in catalog.keyboard_targets.values()]
            errors=[math.dist(a,b) for a,b in zip(actual,predicted)]
            row['conditions'][condition]=dict(mean_key_error_mm=float(np.mean(errors)),maximum_key_error_mm=max(errors),
                center_error_mm=math.dist(pose[:2],truth[:2]),within_1mm_count=sum(e<=1 for e in errors),large_error=max(errors)>3)
        cases.append(row)
    summaries={}
    for condition in m['conditions']:
        rows=[c['conditions'][condition] for c in cases]
        deltas=[c['conditions'][condition]['mean_key_error_mm']-c['conditions']['base']['mean_key_error_mm'] for c in cases]
        summaries[condition]=dict(images=len(rows),mean_key_error_mm=float(np.mean([r['mean_key_error_mm'] for r in rows])),
            large_error_images=sum(r['large_error'] for r in rows),within_1mm_fraction=sum(r['within_1mm_count'] for r in rows)/(46*len(rows)),
            mean_paired_error_delta_mm=float(np.mean(deltas)),worsened_images=sum(d>0 for d in deltas),
            new_large_error_images=sum(c['conditions'][condition]['large_error'] and not c['conditions']['base']['large_error'] for c in cases))
    report=dict(scope='DEVELOPMENT_ONLY',manifest_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
        image_data_sha256={c:d.hexdigest() for c,d in digests.items()},target_catalog_sha256=catalog.content_sha256,
        summaries=summaries,cases=cases,hardware_writes=0,physical_movements=0,qualification_installed=False,
        limitations=['Each added perturbation shares the same base render; base already contains random nuisance effects',
                    'Fixed synthetic strengths/location do not represent measured camera lighting or arm geometry',
                    'Single-perturbation effects do not measure interactions; no inference-time truth input',
                    'Reused development groups; descriptive paired evidence, not held-out qualification'])
    (AI/'eval/single_perturbations_v0_scorecard.json').write_bytes((json.dumps(report,indent=2)+'\n').encode())
    print(json.dumps(summaries,indent=2))


if __name__=='__main__':run()
