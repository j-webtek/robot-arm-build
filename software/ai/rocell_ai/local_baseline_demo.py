"""Offline keyboard preview. Ground truth is display-only, never admission evidence."""
from __future__ import annotations
import argparse
import base64
import hashlib
from io import BytesIO
import json
import math
from pathlib import Path
import sys
AI=Path(__file__).resolve().parents[1];ROOT=AI.parents[1]
sys.path[:0]=[str(AI),str(AI.parent/'src')]
import numpy as np
import torch
from rocell.application import load_simulation_context
from rocell_ai.grounded import propose
from rocell_ai.adapter import inspect
from rocell_ai.shared_shadow_runner_v2 import run_shared_shadow_v2
from vision.pose_model import KeyboardPoseNet
from vision.train_pose import _pose_from_prediction
from vision.landmark_occlusions import render_controlled
from vision.synthetic_keyboard import catalog_for_workspace,transform_target
from vision.evaluate_dark_only_normalization import normalize


def semantic(request, observation):
    proposal=propose(request_id='local-baseline',request=request,observation=observation)
    return proposal,inspect(proposal,observation)


def html_document(report):
    data=json.dumps(report,ensure_ascii=True,allow_nan=False).replace('<',r'\u003c').replace('>',r'\u003e').replace('&',r'\u0026')
    return (AI/'rocell_ai/local_baseline_demo.html').read_text(encoding='utf-8').replace('__REPORT_JSON__',data)


def build_case(case, model, catalog, context):
    image,label,_=render_controlled(case['seed'],catalog,case['condition'],'ellipse')
    stream=BytesIO();image.save(stream,format='PNG');png=stream.getvalue()
    observation=dict(ref='synthetic-'+hashlib.sha256(png).hexdigest(),fresh=case['fresh'],obstructed=case['obstructed'],phone_state='not_visible')
    proposal,inspection=semantic(case['request'],observation)
    # No precision/uncertainty fixture is fabricated from simulation truth.
    terminal=run_shared_shadow_v2(request_id='local-baseline',request=case['request'],observation=observation,context=context,inputs=None)
    normalized,_=normalize(image)
    x=torch.from_numpy(np.asarray(normalized.resize((128,96))).transpose(2,0,1).copy())[None].float()/255
    with torch.no_grad():pose=_pose_from_prediction(model(x)[0])
    targets=[]
    if inspection['status']=='accepted' and proposal['device']=='keyboard':
        for i,action in enumerate(inspection['action_plan']['actions']):
            target=catalog.keyboard_targets[action['key']]
            pred=transform_target(target.center.x,target.center.y,pose[:2],pose[2])
            truth=transform_target(target.center.x,target.center.y,label['pose'][:2],label['pose'][2])
            targets.append(dict(action_index=i,target_id=action['key'],predicted_xy_mm=list(pred),simulation_truth_xy_mm=list(truth),error_mm=math.dist(pred,truth)))
    return dict(**case,image_data_uri='data:image/png;base64,'+base64.b64encode(png).decode(),image_sha256=hashlib.sha256(png).hexdigest(),
        observation=observation,proposal=proposal,semantic_inspection=inspection,
        motion_status=terminal['status'],motion_reason=terminal['reason'],shared_shadow_sha256=terminal['shared_shadow_sha256'],
        predicted_pose=list(pose),targets=targets,coordinate_frame='synthetic_board',coordinate_unit='mm',
        maximum_requested_target_error_mm=max((t['error_mm'] for t in targets),default=None),
        motion_batch=None,hardware_writes=0,physical_movements=0)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=AI/'eval/local_baseline_demo_v0')
    parser.add_argument('--request',help='Optional additional request, evaluated on the first synthetic scene')
    args=parser.parse_args()
    plan_path=AI/'eval/local_baseline_demo_v0_plan.json';plan=json.loads(plan_path.read_text())
    for name,digest in plan['file_sha256'].items():
        if hashlib.sha256((ROOT/name).read_bytes()).hexdigest()!=digest:raise ValueError('Frozen input changed: '+name)
    if args.output.exists():raise FileExistsError('Choose a new output directory: '+str(args.output))
    torch.set_num_threads(4);model=KeyboardPoseNet().eval()
    model.load_state_dict(torch.load(ROOT/plan['checkpoint'],map_location='cpu',weights_only=True))
    catalog=catalog_for_workspace(ROOT);context=load_simulation_context(ROOT,ROOT/'software/config/system_manifest.json')
    cases=plan['cases']
    if args.request is not None:cases=cases+[dict(cases[0],name='Your request',request=args.request)]
    report=dict(schema='rocell.local_baseline_demo.v0',plan_sha256=hashlib.sha256(plan_path.read_bytes()).hexdigest(),
        model_sha256=plan['file_sha256'][plan['checkpoint']],target_catalog_sha256=catalog.content_sha256,
        cases=[build_case(c,model,catalog,context) for c in cases],hardware_writes=0,physical_movements=0,qualification_installed=False,
        limitations=['Synthetic keyboard scenes only; no live camera, phone perception, LLM or hardware execution',
        'Text uses the existing deterministic grounded parser; pose uses the actual local checkpoint',
        'Freshness and obstruction are declared fixture inputs, not model detections',
        'Synthetic board XY is not calibrated physical coordinates; no Z/contact inference',
        'Simulator truth is displayed for scoring only; it never enters the shadow runner',
        'All supported motions require missing qualified perception evidence; no ModelMotionBatch emitted'])
    args.output.mkdir(parents=True)
    (args.output/'report.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    (args.output/'index.html').write_text(html_document(report),encoding='utf-8')
    print(json.dumps([dict(name=c['name'],semantic=c['semantic_inspection']['status'],motion=c['motion_status'],targets=len(c['targets']),max_error_mm=c['maximum_requested_target_error_mm']) for c in report['cases']],indent=2))


if __name__=='__main__':main()
