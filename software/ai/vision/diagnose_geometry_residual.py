"""Oracle counterfactuals for diagnosis only; never runtime calibration."""
import hashlib,json,math,sys
from pathlib import Path
AI=Path(__file__).resolve().parents[1];ROOT=AI.parents[1];sys.path[:0]=[str(AI),str(AI.parent/'src')]
import numpy as np
from vision.landmark_occlusions import render_controlled
from vision.synthetic_keyboard import catalog_for_workspace,transform_target
from vision.geometry_candidate_decoder import fit_pose

def metrics(pose,truth,catalog):
    errors=[math.dist(transform_target(t.center.x,t.center.y,pose[:2],pose[2]),transform_target(t.center.x,t.center.y,truth[:2],truth[2])) for t in catalog.keyboard_targets.values()]
    return dict(mean_mm=float(np.mean(errors)),maximum_mm=max(errors))

def run():
    path=AI/'eval/geometry_residual_v0_plan.json';m=json.loads(path.read_text())
    for f,h in m['file_sha256'].items():assert hashlib.sha256((ROOT/f).read_bytes()).hexdigest()==h
    source=json.loads((AI/'eval/geometry_candidate_v0_report.json').read_text());catalog=catalog_for_workspace(ROOT);rows=[]
    for old in source['rows']:
        _,label,_=render_controlled(old['seed'],catalog,old['condition'],'ellipse');truth=label['pose'];pred=old['candidate']['pose']
        corners=np.array([[p['x_px'],p['y_px']] for p in label['landmarks']]);grid=np.rint(corners/4)*4
        grid_pose,_=fit_pose(grid*np.array([610/256,457/192]))
        poses={'actual':pred,'translation_only':[pred[0],pred[1],truth[2]],'rotation_only':[truth[0],truth[1],pred[2]],'oracle_nearest_grid':grid_pose}
        row=dict(seed=old['seed'],condition=old['condition'],translation_mm=math.dist(pred[:2],truth[:2]),yaw_degrees=abs(math.degrees(math.atan2(math.sin(pred[2]-truth[2]),math.cos(pred[2]-truth[2])))),arms={k:metrics(v,truth,catalog) for k,v in poses.items()})
        assert abs(row['arms']['actual']['mean_mm']-old['arms']['geometry']['mean_mm'])<1e-10
        rows.append(row)
    summaries={}
    for condition in m['conditions']:
        selected=[r for r in rows if r['condition']==condition]
        summaries[condition]={arm:dict(mean_mm=float(np.mean([r['arms'][arm]['mean_mm'] for r in selected])),tail=sum(r['arms'][arm]['maximum_mm']>3 for r in selected)) for arm in poses}
        summaries[condition]['translation_p95_mm']=float(np.percentile([r['translation_mm'] for r in selected],95))
        summaries[condition]['yaw_p95_degrees']=float(np.percentile([r['yaw_degrees'] for r in selected],95))
    report=dict(plan_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),rows=rows,summaries=summaries,hardware_writes=0,physical_movements=0,qualification_installed=False,limitations=['Oracle counterfactuals only; not deployable corrected poses or measured calibration','Translation/rotation errors are nonadditive','Nearest-grid truth is illustrative quantization reference, not a universal accuracy lower bound','Only reused15M development;27M fresh evidence untouched'])
    out=AI/'eval/geometry_residual_v0_report.json'
    if out.exists():raise FileExistsError(out)
    out.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(summaries,indent=2))
if __name__=='__main__':run()
