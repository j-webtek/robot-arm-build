"""Development-only conditional radius from pixel perturbation disagreement."""
import hashlib,json,math,sys
from pathlib import Path
AI=Path(__file__).resolve().parents[1];ROOT=AI.parents[1]
sys.path[:0]=[str(AI),str(AI.parent/'src')]
import numpy as np
import torch
from PIL import Image,ImageEnhance
from vision.pose_model import KeyboardPoseNet
from vision.synthetic_keyboard import render,catalog_for_workspace,transform_target
from vision.evaluate_dark_only_normalization import normalize
from vision.evaluate_pose_challenge import _alter
from vision.train_pose import _pose_from_prediction
from vision.evaluate_localization_radius import empirical_radius
from vision.evaluate_prediction_margin import margin


def shift_image(image,dx,dy):
    pixels=np.asarray(image);h,w=pixels.shape[:2]
    padded=np.pad(pixels,((1,1),(1,1),(0,0)),mode='edge')
    return Image.fromarray(padded[1-dy:1-dy+h,1-dx:1-dx+w].copy())


def undo_shift(pose,dx,dy):
    # Synthetic renderer projection only; never a measured camera transform.
    return (pose[0]-dx*610/128,pose[1]-dy*457/96,pose[2])


def bin_index(disagreement,edges):
    return sum(disagreement>edge for edge in edges)


def run():
    path=AI/'eval/spatial_uncertainty_v0.manifest.json';m=json.loads(path.read_text())
    for f,h in m['file_sha256'].items():
        if hashlib.sha256((ROOT/f).read_bytes()).hexdigest()!=h:raise ValueError('frozen source changed')
    checkpoint=ROOT/m['checkpoint']
    if hashlib.sha256(checkpoint.read_bytes()).hexdigest()!=m['checkpoint_sha256']:raise ValueError('checkpoint changed')
    catalog=catalog_for_workspace(ROOT)
    if catalog.content_sha256!=m['target_catalog_sha256']:raise ValueError('catalog changed')
    model=KeyboardPoseNet();model.load_state_dict(torch.load(checkpoint,map_location='cpu',weights_only=True));model.eval();torch.set_num_threads(4)
    def measure(start,count):
        rows=[]
        for seed in range(start,start+count):
            for condition in m['conditions']:
                image,truth=render(seed,catalog,domain='appearance_shift' if condition=='appearance_shift' else 'standard')
                if condition=='challenge':image=_alter(image,seed)
                image=image.resize((128,96))
                if condition in m['brightness_factors']:image=ImageEnhance.Brightness(image).enhance(m['brightness_factors'][condition])
                image,_=normalize(image)
                variants=[image]+[shift_image(image,dx,dy) for dx,dy in m['pixel_shifts']]
                pixels=np.stack([np.asarray(im,dtype=np.uint8).transpose(2,0,1).copy() for im in variants])
                with torch.no_grad():poses=[_pose_from_prediction(r) for r in model(torch.from_numpy(pixels).float()/255)]
                poses=[poses[0]]+[undo_shift(p,dx,dy) for p,(dx,dy) in zip(poses[1:],m['pixel_shifts'])]
                targets=[[transform_target(r.center.x,r.center.y,p[:2],p[2]) for r in catalog.keyboard_targets.values()] for p in poses]
                disagreement=max(math.dist(a,b) for variant in targets[1:] for a,b in zip(targets[0],variant))
                true=[transform_target(r.center.x,r.center.y,truth[:2],truth[2]) for r in catalog.keyboard_targets.values()]
                rows.append(dict(seed=seed,condition=condition,disagreement_mm=disagreement,bin=bin_index(disagreement,m['bin_edges_mm']),
                    maximum_error_mm=max(math.dist(a,b) for a,b in zip(targets[0],true)),predicted_pose=poses[0],truth_pose=truth,
                    pixels_sha256=hashlib.sha256(pixels.tobytes()).hexdigest()))
        return rows
    fitting=measure(*m['fitting_groups']);radii=[];supports=[]
    for index in range(len(m['bin_edges_mm'])+1):
        by_seed={}
        for r in fitting:
            if r['bin']==index:by_seed[r['seed']]=max(by_seed.get(r['seed'],0),r['maximum_error_mm'])
        supports.append(len(by_seed))
        radii.append(empirical_radius(list(by_seed.values()),.99) if len(by_seed)>=m['minimum_bin_groups'] else None)
    # All radii fixed before evaluation of the separate reused development groups.
    evaluation=measure(*m['development_groups'])
    for r in evaluation:
        radius=radii[r['bin']];r['radius_mm']=radius
        r['accepted']=radius is not None and radius<=m['maximum_admitted_radius_mm']
        r['covered']=r['maximum_error_mm']<=radius if r['accepted'] else None
        r['all_targets_fit']=None
        if r['accepted']:
            pred=r['predicted_pose'];truth=r['truth_pose']
            r['all_targets_fit']=all(margin(transform_target(t.center.x,t.center.y,pred[:2],pred[2]),
                transform_target(t.center.x,t.center.y,truth[:2],truth[2]),truth[2],(t.half_extent_x_mm,t.half_extent_y_mm),radius)>=0 for t in catalog.keyboard_targets.values())
    metrics={}
    for condition in m['conditions']:
        rows=[r for r in evaluation if r['condition']==condition];accepted=[r for r in rows if r['accepted']]
        metrics[condition]=dict(images=len(rows),accepted=len(accepted),acceptance_fraction=len(accepted)/len(rows),
            coverage=sum(r['covered'] for r in accepted)/len(accepted) if accepted else None,
            containment=sum(r['all_targets_fit'] for r in accepted)/len(accepted) if accepted else None)
    groups=[]
    for seed in range(m['development_groups'][0],sum(m['development_groups'])):
        accepted=[r for r in evaluation if r['seed']==seed and r['accepted']]
        if accepted:groups.append(dict(seed=seed,covered=all(r['covered'] for r in accepted),fit=all(r['all_targets_fit'] for r in accepted)))
    group_coverage=sum(g['covered'] for g in groups)/len(groups) if groups else None
    group_fit=sum(g['fit'] for g in groups)/len(groups) if groups else None
    passed=bool(groups) and group_coverage>=.95 and group_fit>=.95 and all(v['acceptance_fraction']>=.10 and v['coverage']>=.95 and v['containment']>=.95 for v in metrics.values())
    report=dict(scope='REUSED_DEVELOPMENT_FEASIBILITY',manifest_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
        radii_mm=radii,bin_support_groups=supports,fitting_cases=fitting,evaluation_cases=evaluation,metrics=metrics,
        accepted_groups=groups,group_coverage=group_coverage,group_containment=group_fit,feasibility_passed=passed,
        hardware_writes=0,physical_movements=0,qualification_installed=False,
        limitations=['Fitting seeds overlap pose training; development seeds were reused for selection; optimistic feasibility only',
                    'Spatial stability may miss shared bias; edge padding can cause artifacts; synthetic inverse projection is not runtime calibration',
                    'Oracle geometry is scoring-only; abstained examples never counted as successful coverage',
                    'No runtime installation or fresh held-out evidence; a pass requires separate fresh calibration/evaluation'])
    (AI/'eval/spatial_uncertainty_v0_report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(radii=radii,support=supports,metrics=metrics,group_coverage=group_coverage,group_fit=group_fit,passed=passed),indent=2))


if __name__=='__main__':run()
