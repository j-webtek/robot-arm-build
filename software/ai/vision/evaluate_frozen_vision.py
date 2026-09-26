"""Frozen synthetic-view benchmark of actual precision and scene-model outputs."""
import argparse
import hashlib
from io import BytesIO
import json
import math
from pathlib import Path
import sys

AI_DIR=Path(__file__).resolve().parents[1]
ROOT=AI_DIR.parents[1]
sys.path[:0]=[str(AI_DIR),str(AI_DIR.parent/'src')]
import numpy as np
import torch
from vision.pose_model import KeyboardPoseNet
from vision.synthetic_keyboard import render, catalog_for_workspace, transform_target
from vision.evaluate_pose_challenge import _alter
from vision.train_pose import _pose_from_prediction
from rocell_ai.scene_observation import FrameEvidence, canonical_hash
from rocell_ai.pixel_quality import assess
from rocell_ai.vision_runtime import OllamaVisionObserver


def evaluate(manifest_path, checkpoint):
    manifest=json.loads(manifest_path.read_text())
    for relative, expected in manifest['file_sha256'].items():
        if hashlib.sha256((ROOT/relative).read_bytes()).hexdigest()!=expected:
            raise ValueError('Frozen file changed: '+relative)
    if hashlib.sha256(checkpoint.read_bytes()).hexdigest()!=manifest['checkpoint_sha256']:
        raise ValueError('Frozen checkpoint changed')
    torch.set_num_threads(4)
    model=KeyboardPoseNet()
    model.load_state_dict(torch.load(checkpoint,map_location='cpu',weights_only=True));model.eval()
    observer=OllamaVisionObserver(endpoint='http://127.0.0.1:11434',model=manifest['observer_model'],
        model_identity=manifest['observer_identity'],timeout_seconds=60,context_tokens=8192)
    catalog=catalog_for_workspace(ROOT)
    rows=[]
    for case in manifest['cases']:
        image,truth=render(case['seed'],catalog,domain='appearance_shift' if case['condition']=='appearance_shift' else 'standard')
        if case['condition']=='challenge': image=_alter(image,case['seed'])
        stream=BytesIO();image.save(stream,format='PNG')
        frame=FrameEvidence(case['case_id'],'2026-09-26T00:00:00Z',stream.getvalue())
        pixels=np.asarray(image.resize((128,96)),dtype=np.uint8).transpose(2,0,1).copy()
        with torch.no_grad(): predicted=_pose_from_prediction(model(torch.from_numpy(pixels).unsqueeze(0).float()/255)[0])
        errors={}
        for key,region in catalog.keyboard_targets.items():
            actual=transform_target(region.center.x,region.center.y,truth[:2],truth[2])
            estimated=transform_target(region.center.x,region.center.y,predicted[:2],predicted[2])
            errors[key]=math.dist(actual,estimated)
        scene=observer.observe(frame)
        pixel=assess(frame)
        accepted=not scene['abstain'] and pixel['accepted']
        maximum=max(errors.values())
        rows.append({**case,'image_sha256':frame.image_sha256,'truth_pose':list(truth),'predicted_pose':list(predicted),
                     'key_error_mm':errors,'maximum_key_error_mm':maximum,'scene_observation':scene,'pixel_quality':pixel,
                     'quality_accepted':accepted,'diagnostic_over_budget':maximum>manifest['diagnostic_error_budget_mm'],
                     'accepted_over_budget':accepted and maximum>manifest['diagnostic_error_budget_mm']})
        print(case['case_id'], 'max error',round(maximum,2),'quality accepted',accepted,flush=True)
    summary={}
    for condition in sorted({r['condition'] for r in rows}):
        group=[r for r in rows if r['condition']==condition]
        summary[condition]={'cases':len(group),'key_error_mm_p95':float(np.percentile([e for r in group for e in r['key_error_mm'].values()],95)),
                            'quality_accepted':sum(r['quality_accepted'] for r in group),
                            'accepted_over_budget':sum(r['accepted_over_budget'] for r in group)}
    core={'schema':'rocell.ai_frozen_vision_benchmark.v0','manifest_sha256':hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
          'checkpoint_sha256':manifest['checkpoint_sha256'],'summary':summary,'cases':rows,
          'physical_execution_authorized':False,'hardware_writes':0,
          'limitations':['24 correlated procedural images in eight seed groups; no physical camera evaluation',
                         'Synthetic top-down projection is a camera proxy, not measured deployment intrinsics or perspective',
                         'No photo texture or phone scenes in this benchmark',
                         '5 mm is a diagnostic budget, not a qualified physical contact tolerance',
                         'Scene/pixel quality acceptance is not full vision fusion or coordinate admission',
                         'No route simulation, controller commands, or physical input events in this evaluation']}
    return {**core,'report_sha256':canonical_hash(core)}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest',type=Path,default=AI_DIR/'eval/frozen_vision_v0.manifest.json')
    parser.add_argument('--checkpoint',type=Path,default=AI_DIR/'train/runs/synthetic_pose_photo_v1/pose_model.pt')
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    result=evaluate(args.manifest,args.checkpoint)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_bytes((json.dumps(result,indent=2,sort_keys=True)+'\n').encode())
