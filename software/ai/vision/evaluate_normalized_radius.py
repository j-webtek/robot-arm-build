"""Empirical localization-radius calibration, followed by untouched evaluation.

The unit is a seed group: maximum key error across all keys and seven conditions.
This estimates empirical coverage only, with no distribution-free or physical claim.
"""
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
from PIL import ImageEnhance
from vision.evaluate_dark_only_normalization import normalize
from vision.pose_model import KeyboardPoseNet
from vision.synthetic_keyboard import render,catalog_for_workspace,transform_target
from vision.evaluate_pose_challenge import _alter
from vision.train_pose import _pose_from_prediction
from rocell_ai.scene_observation import canonical_hash


def empirical_radius(scores, coverage):
    if not scores or any(type(s) not in (int,float) or not math.isfinite(s) or s<0 for s in scores):
        raise ValueError('Scores must be nonempty finite nonnegative errors')
    if type(coverage) not in (int,float) or not 0<coverage<1:
        raise ValueError('Coverage must be between zero and one')
    return sorted(scores)[math.ceil(coverage*len(scores))-1]


def evaluate(manifest_path,checkpoint):
    manifest=json.loads(manifest_path.read_text())
    for relative,digest in manifest['file_sha256'].items():
        if hashlib.sha256((ROOT/relative).read_bytes()).hexdigest()!=digest:
            raise ValueError('Frozen source changed: '+relative)
    if hashlib.sha256(checkpoint.read_bytes()).hexdigest()!=manifest['checkpoint_sha256']:
        raise ValueError('Frozen checkpoint changed')
    catalog=catalog_for_workspace(ROOT)
    if catalog.content_sha256!=manifest['target_catalog_sha256']:
        raise ValueError('Frozen catalog changed')
    calibration_seeds=manifest['calibration_seeds'];evaluation_seeds=manifest['evaluation_seeds']
    if set(calibration_seeds)&set(evaluation_seeds):
        raise ValueError('Calibration/evaluation seeds overlap')
    torch.set_num_threads(4)
    model=KeyboardPoseNet();model.load_state_dict(torch.load(checkpoint,map_location='cpu',weights_only=True));model.eval()

    def measure(seeds):
        groups=[]
        for seed in seeds:
            cases=[]
            for condition in manifest['conditions']:
                image,truth=render(seed,catalog,domain='appearance_shift' if condition=='appearance_shift' else 'standard')
                if condition=='challenge': image=_alter(image,seed)
                image=image.resize((128,96))
                if condition in manifest['brightness_factors']:image=ImageEnhance.Brightness(image).enhance(manifest['brightness_factors'][condition])
                image,gain=normalize(image)
                stream=BytesIO();image.save(stream,format='PNG')
                pixels=np.asarray(image.resize((128,96)),dtype=np.uint8).transpose(2,0,1).copy()
                with torch.no_grad(): prediction=_pose_from_prediction(model(torch.from_numpy(pixels).unsqueeze(0).float()/255)[0])
                errors={}
                for key,region in catalog.keyboard_targets.items():
                    actual=transform_target(region.center.x,region.center.y,truth[:2],truth[2])
                    estimated=transform_target(region.center.x,region.center.y,prediction[:2],prediction[2])
                    errors[key]=math.dist(actual,estimated)
                worst=max(errors,key=errors.get)
                cases.append({'condition':condition,'normalization_gain':gain,'image_sha256':hashlib.sha256(stream.getvalue()).hexdigest(),
                              'truth_pose':list(truth),'predicted_pose':list(prediction),'worst_key':worst,
                              'maximum_key_error_mm':errors[worst]})
            groups.append({'seed':seed,'cases':cases,'maximum_error_mm':max(c['maximum_key_error_mm'] for c in cases)})
        return groups

    calibration=measure(calibration_seeds)
    radius=empirical_radius([g['maximum_error_mm'] for g in calibration],manifest['empirical_coverage_target'])
    # The radius is fixed before evaluation labels are computed or inspected.
    evaluation=measure(evaluation_seeds)
    covered=sum(g['maximum_error_mm']<=radius for g in evaluation)
    fit=[key for key,region in catalog.keyboard_targets.items() if radius<=min(region.half_extent_x_mm,region.half_extent_y_mm)]
    core={'schema':'rocell.ai_localization_radius_study.v0',
          'manifest_sha256':hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
          'checkpoint_sha256':manifest['checkpoint_sha256'],'target_catalog_sha256':catalog.content_sha256,
          'calibration_data_sha256':canonical_hash(calibration),'evaluation_data_sha256':canonical_hash(evaluation),
          'calibration_groups':calibration,'evaluation_groups':evaluation,
          'empirical_radius_mm':radius,'empirical_coverage_target':manifest['empirical_coverage_target'],
          'evaluation_covered_groups':covered,'evaluation_group_count':len(evaluation),
          'evaluation_empirical_coverage':covered/len(evaluation),
          'nominal_center_targets_fitting_radius':fit,'target_count':len(catalog.keyboard_targets),
          'qualification_installed':False,'qualification':None,'physical_execution_authorized':False,'hardware_writes':0,
          'limitations':['Empirical nearest-rank calibration, not a statistical coverage guarantee',
                         'Group score is worst error over 46 keys and seven correlated conditions',
                         'Fixed synthetic projection and shared renderer family; no measured deployment domain',
                         'Center-fit test is an optimistic geometric diagnostic; no motion admission or physical contact',
                         'No model retraining, scene-model inference, or qualification registry change']}
    return {**core,'study_sha256':canonical_hash(core)}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest',type=Path,default=AI_DIR/'eval/localization_radius_v0.manifest.json')
    parser.add_argument('--checkpoint',type=Path,default=AI_DIR/'train/runs/synthetic_pose_photo_v1/pose_model.pt')
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();result=evaluate(args.manifest,args.checkpoint)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_bytes((json.dumps(result,indent=2,sort_keys=True)+'\n').encode())
    print(json.dumps({k:v for k,v in result.items() if k not in ('calibration_groups','evaluation_groups')},indent=2))
