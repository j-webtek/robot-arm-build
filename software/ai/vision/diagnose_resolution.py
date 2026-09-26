"""Development-only sensitivity to inference resolution; never qualification."""
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
    path=AI/'eval/resolution_development_v0.manifest.json'
    m=json.loads(path.read_text())
    for f,h in m['file_sha256'].items():
        if hashlib.sha256((ROOT/f).read_bytes()).hexdigest()!=h: raise ValueError('frozen source changed')
    checkpoint=AI/'results/robust_pose_v0/pose_model.pt'
    if hashlib.sha256(checkpoint.read_bytes()).hexdigest()!=m['checkpoint_sha256']: raise ValueError('checkpoint changed')
    torch.set_num_threads(4)
    model=KeyboardPoseNet();model.load_state_dict(torch.load(checkpoint,weights_only=True,map_location='cpu'));model.eval()
    catalog=catalog_for_workspace(ROOT)
    buckets={str(size):{c:[] for c in m['conditions']} for size in m['sizes']}
    groups={str(size):[] for size in m['sizes']}
    digest=hashlib.sha256()
    for seed in range(m['seed_start'],m['seed_start']+m['seed_count']):
        worst={str(size):0 for size in m['sizes']}
        for condition in m['conditions']:
            image,truth=render(seed,catalog,domain='appearance_shift' if condition=='appearance_shift' else 'standard')
            if condition=='challenge': image=_alter(image,seed)
            digest.update(image.tobytes())
            actual=[transform_target(r.center.x,r.center.y,truth[:2],truth[2]) for r in catalog.keyboard_targets.values()]
            for size in m['sizes']:
                pixels=np.asarray(image.resize(tuple(size)),dtype=np.uint8).transpose(2,0,1).copy()
                with torch.no_grad(): prediction=_pose_from_prediction(model(torch.from_numpy(pixels).unsqueeze(0).float()/255)[0])
                predicted=[transform_target(r.center.x,r.center.y,prediction[:2],prediction[2]) for r in catalog.keyboard_targets.values()]
                errors=[math.dist(a,b) for a,b in zip(actual,predicted)]
                buckets[str(size)][condition].extend(errors);worst[str(size)]=max(worst[str(size)],max(errors))
        for size,value in worst.items(): groups[size].append(value)
    def metrics(errors):
        return dict(count=len(errors),mean_mm=float(np.mean(errors)),p95_mm=float(np.percentile(errors,95)),
                    maximum_mm=max(errors),within_1mm_fraction=sum(e<=1 for e in errors)/len(errors))
    result=dict(scope='DEVELOPMENT_ONLY',manifest_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
        image_data_sha256=digest.hexdigest(),target_catalog_sha256=catalog.content_sha256,
        results={size:dict(conditions={c:metrics(v) for c,v in values.items()},
                          all=metrics([e for v in values.values() for e in v]),
                          seed_group_maximum_error=metrics(groups[size])) for size,values in buckets.items()},
        resolution_scale={str(size):dict(mm_per_pixel_x=610/size[0],mm_per_pixel_y=457/size[1],
                                        one_mm_pixels_x=size[0]/610,one_mm_pixels_y=size[1]/457) for size in m['sizes']},
        hardware_writes=0,physical_movements=0,qualification_installed=False,
        limitations=['256x192 inference is off the trained 128x96 input distribution; this is not a matched-resolution training comparison',
                    'Subpixel regression is possible; pixel scale alone does not establish an accuracy floor',
                    'Synthetic renderer rasterizes at 256x192; upsampling cannot create new physical evidence',
                    'Development groups only; no calibration/evaluation seeds accessed; correlated sample counts'])
    (AI/'eval/resolution_development_v0_scorecard.json').write_bytes((json.dumps(result,indent=2)+'\n').encode())
    print(json.dumps({k:v['all'] for k,v in result['results'].items()}))


if __name__=='__main__': run()
