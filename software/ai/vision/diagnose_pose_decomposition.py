"""Development-only translation/rotation counterfactual error decomposition."""
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
    path=AI/'eval/pose_decomposition_v0.manifest.json'
    m=json.loads(path.read_text())
    for f,h in m['file_sha256'].items():
        if hashlib.sha256((ROOT/f).read_bytes()).hexdigest()!=h: raise ValueError('frozen source changed')
    checkpoint=AI/'results/matched_resolution_v0_128/pose_model.pt'
    if hashlib.sha256(checkpoint.read_bytes()).hexdigest()!=m['checkpoint_sha256']: raise ValueError('checkpoint changed')
    torch.set_num_threads(4)
    model=KeyboardPoseNet();model.load_state_dict(torch.load(checkpoint,weights_only=True,map_location='cpu'));model.eval()
    catalog=catalog_for_workspace(ROOT)
    buckets={method:{c:[] for c in m['conditions']} for method in m['methods']}
    groups={method:[] for method in m['methods']}
    digest=hashlib.sha256();pose_errors={c:[] for c in m["conditions"]}
    for seed in range(m['seed_start'],m['seed_start']+m['seed_count']):
        worst={method:0 for method in m['methods']}
        for condition in m['conditions']:
            image,truth=render(seed,catalog,domain='appearance_shift' if condition=='appearance_shift' else 'standard')
            if condition=='challenge': image=_alter(image,seed)
            digest.update(image.tobytes())
            actual=[transform_target(r.center.x,r.center.y,truth[:2],truth[2]) for r in catalog.keyboard_targets.values()]
            pixels=np.asarray(image.resize((128,96)),dtype=np.uint8).transpose(2,0,1).copy()
            with torch.no_grad(): prediction=_pose_from_prediction(model(torch.from_numpy(pixels).unsqueeze(0).float()/255)[0])
            pose_errors[condition].append(dict(seed=seed,translation_mm=math.dist(prediction[:2],truth[:2]),
                yaw_degrees=abs(math.degrees(math.atan2(math.sin(prediction[2]-truth[2]),math.cos(prediction[2]-truth[2]))))))
            predicted=[transform_target(r.center.x,r.center.y,prediction[:2],prediction[2]) for r in catalog.keyboard_targets.values()]
            for method in m['methods']:
                if method=='baseline': points=predicted
                elif method=='translation_only':
                    points=[transform_target(r.center.x,r.center.y,prediction[:2],truth[2]) for r in catalog.keyboard_targets.values()]
                else:
                    points=[transform_target(r.center.x,r.center.y,truth[:2],prediction[2]) for r in catalog.keyboard_targets.values()]
                errors=[math.dist(a,b) for a,b in zip(actual,points)]
                buckets[method][condition].extend(errors);worst[method]=max(worst[method],max(errors))
        for size,value in worst.items(): groups[size].append(value)
    def metrics(errors):
        return dict(count=len(errors),mean_mm=float(np.mean(errors)),p95_mm=float(np.percentile(errors,95)),
                    maximum_mm=max(errors),within_1mm_fraction=sum(e<=1 for e in errors)/len(errors))
    result=dict(scope='DEVELOPMENT_ONLY',manifest_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
        image_data_sha256=digest.hexdigest(),target_catalog_sha256=catalog.content_sha256,
        results={size:dict(conditions={c:metrics(v) for c,v in values.items()},
                          all=metrics([e for v in values.values() for e in v]),
                          seed_group_maximum_error=metrics(groups[size])) for size,values in buckets.items()},
        pose_components={c:dict(translation_mean_mm=float(np.mean([r['translation_mm'] for r in rows])),
            translation_p95_mm=float(np.percentile([r['translation_mm'] for r in rows],95)),
            yaw_mean_degrees=float(np.mean([r['yaw_degrees'] for r in rows])),
            yaw_p95_degrees=float(np.percentile([r['yaw_degrees'] for r in rows],95))) for c,rows in pose_errors.items()},
        hardware_writes=0,physical_movements=0,qualification_installed=False,
        limitations=['Development selection evidence only; no calibration/evaluation seeds accessed',
                    'Fixed synthetic projection; no physical camera calibration',
                    'Counterfactual components use hidden truth for scoring only; scalar errors are not additive',
                    'Condition bundles do not isolate lighting or obstruction causes; no per-image occlusion labels exist'])
    (AI/'eval/pose_decomposition_v0_scorecard.json').write_bytes((json.dumps(result,indent=2)+'\n').encode())
    print(json.dumps({k:v['all'] for k,v in result['results'].items()}))


if __name__=='__main__': run()
