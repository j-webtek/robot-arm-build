"""Causal renderer-layer intervention, research only."""
import hashlib,json,sys
from pathlib import Path
AI=Path(__file__).resolve().parents[1];ROOT=AI.parents[1];sys.path[:0]=[str(AI),str(AI.parent/'src')]
import numpy as np
import torch
from vision.clutter_ablation_occlusions import render_controlled
from vision.landmark_occlusions import render_controlled as original
from vision.synthetic_keyboard import catalog_for_workspace
from vision.evaluate_dark_only_normalization import normalize
from vision.pose_model import KeyboardPoseNet
from vision.train_pose import _pose_from_prediction
from vision.diagnose_pose_tail import decompose


def run():
    p=AI/'eval/clutter_ablation_v0_plan.json';plan=json.loads(p.read_text())
    for f,h in plan['file_sha256'].items():assert hashlib.sha256((ROOT/f).read_bytes()).hexdigest()==h
    out=AI/'eval/clutter_ablation_v0_report.json'
    if out.exists():raise FileExistsError(out)
    torch.set_num_threads(4);model=KeyboardPoseNet();model.load_state_dict(torch.load(ROOT/plan['checkpoint'],map_location='cpu',weights_only=True));model.eval();catalog=catalog_for_workspace(ROOT)
    old=json.loads((AI/'eval/pose_landmark_v0_report.json').read_text());persistent=json.loads((AI/'eval/persistent_pose_v0_report.json').read_text());hard={(r['seed'],r['condition']) for r in persistent['rows'] if r['trained_failure_count']==6}
    rows=[];hashes={m:hashlib.sha256() for m in plan['modes']}
    for prior in old['rows']:
        seed,c=prior['seed'],prior['condition'];ref,label,mask=original(seed,catalog,c,'ellipse');row=dict(seed=seed,condition=c,persistent=(seed,c) in hard,modes={})
        for mode,remove in plan['modes'].items():
            image,lab,newmask=render_controlled(seed,catalog,c,'ellipse',frozenset(remove));assert lab['pose']==label['pose']
            if mode=='original':assert image.tobytes()==ref.tobytes() and lab==label and newmask.tobytes()==mask.tobytes()
            changed=image.tobytes()!=ref.tobytes();image,_=normalize(image);hashes[mode].update(image.tobytes())
            with torch.no_grad():pose=_pose_from_prediction(model(torch.from_numpy(np.asarray(image.resize((128,96))).transpose(2,0,1).copy())[None].float()/255)[0])
            metrics=decompose(pose,lab['pose'],catalog.keyboard_targets.values())
            if mode=='original':assert all(abs(metrics[k]-v)<1e-9 for k,v in prior['arms']['pose'].items())
            row['modes'][mode]=dict(changed=changed,**metrics)
        rows.append(row)
    summaries={}
    for mode in plan['modes']:
        summaries[mode]={}
        for c in plan['conditions']:
            selected=[r for r in rows if r['condition']==c];m=[r['modes'][mode] for r in selected]
            summaries[mode][c]=dict(mean_mm=float(np.mean([v['mean_mm'] for v in m])),tail=sum(v['maximum_mm']>3 for v in m),changed=sum(v['changed'] for v in m),
                recovered=sum(r['modes']['original']['maximum_mm']>3 and r['modes'][mode]['maximum_mm']<=3 for r in selected),introduced=sum(r['modes']['original']['maximum_mm']<=3 and r['modes'][mode]['maximum_mm']>3 for r in selected),persistent_remaining=sum(r['persistent'] and r['modes'][mode]['maximum_mm']>3 for r in selected))
    result=dict(plan_sha256=hashlib.sha256(p.read_bytes()).hexdigest(),pixels_sha256={m:h.hexdigest() for m,h in hashes.items()},rows=rows,summaries=summaries,hardware_writes=0,physical_movements=0,qualification_installed=False,limitations=['Baseline checkpoint only; causal claim limited to synthetic layer removal','Blur/contrast/normalization can propagate removed-layer effects across pixels','Reused development; original cases remain authoritative for accuracy; no runtime clutter removal'])
    out.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(summaries,indent=2))
if __name__=='__main__':run()
