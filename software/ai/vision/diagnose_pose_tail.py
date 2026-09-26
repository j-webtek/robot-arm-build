"""Oracle decomposition for research only; never runtime calibration."""
import hashlib,json,math,sys
from pathlib import Path
AI=Path(__file__).resolve().parents[1];ROOT=AI.parents[1];sys.path[:0]=[str(AI),str(AI.parent/'src')]
import numpy as np
import torch
from vision.pose_model import KeyboardPoseNet
from vision.train_pose import _pose_from_prediction
from vision.landmark_occlusions import render_controlled
from vision.synthetic_keyboard import catalog_for_workspace,transform_target
from vision.evaluate_dark_only_normalization import normalize


def decompose(prediction,truth,targets):
    def errors(pose):
        return [math.dist(transform_target(t.center.x,t.center.y,pose[:2],pose[2]),transform_target(t.center.x,t.center.y,truth[:2],truth[2])) for t in targets]
    combined=errors(prediction)
    translation=math.dist(prediction[:2],truth[:2])
    rotation=max(errors([*truth[:2],prediction[2]]))
    return dict(mean_mm=float(np.mean(combined)),maximum_mm=max(combined),translation_mm=translation,rotation_only_maximum_mm=rotation,
        translation_delta_mm=[prediction[i]-truth[i] for i in range(2)],
        yaw_degrees=abs(math.degrees(math.atan2(math.sin(prediction[2]-truth[2]),math.cos(prediction[2]-truth[2])))))


def run():
    plan_path=AI/'eval/pose_tail_v0_plan.json';plan=json.loads(plan_path.read_text())
    for f,h in plan['file_sha256'].items():assert hashlib.sha256((ROOT/f).read_bytes()).hexdigest()==h
    model=KeyboardPoseNet();model.load_state_dict(torch.load(ROOT/plan['checkpoint'],map_location='cpu',weights_only=True));model.eval();torch.set_num_threads(4)
    source=json.loads((AI/'eval/pose_landmark_v0_report.json').read_text());catalog=catalog_for_workspace(ROOT);rows=[];pixels=hashlib.sha256()
    for old in source['rows']:
        image,label,_=render_controlled(old['seed'],catalog,old['condition'],'ellipse');image,_=normalize(image)
        pixels.update(np.asarray(image).transpose(2,0,1).copy().tobytes())
        with torch.no_grad():prediction=_pose_from_prediction(model(torch.from_numpy(np.asarray(image.resize((128,96))).transpose(2,0,1).copy())[None].float()/255)[0])
        metrics=decompose(prediction,label['pose'],catalog.keyboard_targets.values())
        assert all(abs(metrics[k]-v)<1e-9 for k,v in old['arms']['pose'].items())
        rows.append(dict(seed=old['seed'],condition=old['condition'],prediction=list(prediction),truth=label['pose'],**metrics))
    assert pixels.hexdigest()==source['development_pixels_sha256']
    baseline={r['seed']:r for r in rows if r['condition']=='standard'};summaries={}
    for c in plan['conditions']:
        selected=[r for r in rows if r['condition']==c];bad=[r for r in selected if r['maximum_mm']>3]
        summaries[c]=dict(cases=len(selected),bad=len(bad),bad_seeds=[r['seed'] for r in bad],
            translation_larger_in_bad=sum(r['translation_mm']>=r['rotation_only_maximum_mm'] for r in bad),
            translation_alone_over3=sum(r['translation_mm']>3 for r in bad),rotation_alone_over3=sum(r['rotation_only_maximum_mm']>3 for r in bad),
            bad_translation_mean_mm=float(np.mean([r['translation_mm'] for r in bad])),bad_rotation_mean_mm=float(np.mean([r['rotation_only_maximum_mm'] for r in bad])),
            new_bad_vs_standard=[r['seed'] for r in bad if baseline[r['seed']]['maximum_mm']<=3],
            recovered_vs_standard=[r['seed'] for r in selected if r['maximum_mm']<=3 and baseline[r['seed']]['maximum_mm']>3],
            mean_maximum_error_change_mm=float(np.mean([r['maximum_mm']-baseline[r['seed']]['maximum_mm'] for r in selected])))
    report=dict(plan_sha256=hashlib.sha256(plan_path.read_bytes()).hexdigest(),development_pixels_sha256=pixels.hexdigest(),rows=rows,summaries=summaries,
        hardware_writes=0,physical_movements=0,qualification_installed=False,limitations=['Reused synthetic development; oracle decomposition only','Translation and rotation magnitudes do not add exactly; they can reinforce or cancel','Paired interventions support only this synthetic renderer, not real lighting or arm geometry'])
    output=AI/'eval/pose_tail_v0_report.json'
    if output.exists():raise FileExistsError(output)
    output.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(summaries,indent=2))
if __name__=='__main__':run()
