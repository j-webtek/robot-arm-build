"""Evaluation-only key margin study; hidden truth never supplies runtime authority."""
import argparse
import hashlib
import json
import math
from pathlib import Path
from vision.evaluate_localization_radius import (
    ROOT, np, torch, KeyboardPoseNet, render, catalog_for_workspace,
    transform_target, _alter, _pose_from_prediction, canonical_hash,
)


def margin(point, center, yaw, half_extents, radius):
    values=(*point,*center,yaw,*half_extents,radius)
    if any(type(v) not in (int,float) or not math.isfinite(v) for v in values):
        raise ValueError('Geometry must be finite')
    if radius<0 or min(half_extents)<=0:
        raise ValueError('Invalid radius or extents')
    dx,dy=point[0]-center[0],point[1]-center[1]
    local_x=math.cos(yaw)*dx+math.sin(yaw)*dy
    local_y=-math.sin(yaw)*dx+math.cos(yaw)*dy
    return min(half_extents[0]-abs(local_x)-radius,
               half_extents[1]-abs(local_y)-radius)


def evaluate(manifest_path, checkpoint):
    m=json.loads(manifest_path.read_text(encoding='utf-8'))
    for path,digest in m['file_sha256'].items():
        if hashlib.sha256((ROOT/path).read_bytes()).hexdigest()!=digest:
            raise ValueError('Frozen file changed: '+path)
    if hashlib.sha256(checkpoint.read_bytes()).hexdigest()!=m['checkpoint_sha256']:
        raise ValueError('Checkpoint changed')
    catalog=catalog_for_workspace(ROOT)
    if catalog.content_sha256!=m['target_catalog_sha256']:
        raise ValueError('Catalog changed')
    torch.set_num_threads(4)
    model=KeyboardPoseNet()
    model.load_state_dict(torch.load(checkpoint,map_location='cpu',weights_only=True))
    model.eval()
    cases=[]
    for seed in m['evaluation_seeds']:
        for condition in m['conditions']:
            image,truth=render(seed,catalog,domain='appearance_shift' if condition=='appearance_shift' else 'standard')
            if condition=='challenge': image=_alter(image,seed)
            pixels=np.asarray(image.resize((128,96)),dtype=np.uint8).transpose(2,0,1).copy()
            with torch.no_grad():
                prediction=_pose_from_prediction(model(torch.from_numpy(pixels).unsqueeze(0).float()/255)[0])
            oracle={};nominal={}
            for key,r in catalog.keyboard_targets.items():
                point=transform_target(r.center.x,r.center.y,prediction[:2],prediction[2])
                actual=transform_target(r.center.x,r.center.y,truth[:2],truth[2])
                extents=(r.half_extent_x_mm,r.half_extent_y_mm)
                oracle[key]=margin(point,actual,truth[2],extents,m['radius_mm'])
                nominal[key]=margin(point,(r.center.x,r.center.y),0,extents,m['radius_mm'])
            cases.append(dict(seed=seed,condition=condition,truth_pose=list(truth),predicted_pose=list(prediction),
                oracle_fitting_keys=[k for k,v in oracle.items() if v>=0],
                nominal_fitting_keys=[k for k,v in nominal.items() if v>=0],
                oracle_minimum_margin_mm=min(oracle.values()),nominal_minimum_margin_mm=min(nominal.values())))
    core=dict(schema='rocell.ai_prediction_margin_study.v0',
        manifest_sha256=hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
        radius_mm=m['radius_mm'],image_count=len(cases),target_count=len(catalog.keyboard_targets),
        oracle_fitting_predictions=sum(len(c['oracle_fitting_keys']) for c in cases),
        nominal_fitting_predictions=sum(len(c['nominal_fitting_keys']) for c in cases),
        oracle_all_keys_fit_images=sum(len(c['oracle_fitting_keys'])==len(catalog.keyboard_targets) for c in cases),
        nominal_all_keys_fit_images=sum(len(c['nominal_fitting_keys'])==len(catalog.keyboard_targets) for c in cases),
        cases=cases,qualification_installed=False,hardware_writes=0,physical_execution_authorized=False,
        limitations=['Oracle regions use hidden rendered truth for scoring only.',
                    'Nominal fit is only the emitter geometry predicate, not complete ingress admission.',
                    'Correlated key/image counts are descriptive, not independent trials.',
                    'No scene-model run, qualification, motion batch, or physical accuracy claim.'])
    return {**core,'report_sha256':canonical_hash(core)}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--manifest',type=Path,required=True)
    p.add_argument('--checkpoint',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();report=evaluate(a.manifest,a.checkpoint)
    a.output.write_bytes((json.dumps(report,indent=2,sort_keys=True)+'\n').encode())
    print(json.dumps({k:v for k,v in report.items() if k!='cases'},indent=2))
