"""Audit existing cohorts and define deterministic scene-group folds; no fitting."""
import hashlib,json,math,sys
from pathlib import Path
AI=Path(__file__).resolve().parents[1];ROOT=AI.parents[1];sys.path[:0]=[str(AI),str(AI.parent/'src')]
import numpy as np
from vision.landmark_occlusions import render_controlled
from vision.synthetic_keyboard import catalog_for_workspace
from vision.evaluate_dark_only_normalization import normalize


def group_folds(seeds):
    seeds=list(seeds)
    if len(set(seeds))!=len(seeds) or not seeds or any(type(s) is not int for s in seeds):raise ValueError('invalid scene seeds')
    folds=[[] for _ in range(5)]
    for corner in range(4):
        ordered=sorted((s for s in seeds if s%4==corner),key=lambda s:hashlib.sha256(f'linear-selection-v1:{s}'.encode()).hexdigest())
        for i,seed in enumerate(ordered):folds[i%5].append(seed)
    return [sorted(f) for f in folds]


def pose_bins(poses):
    poses=np.asarray(poses,dtype=float)
    normalized=(poses-np.array([205.,130.,math.pi-math.radians(11)]))/np.array([60.,48.,math.radians(22)])
    if poses.ndim!=2 or poses.shape[1]!=3 or not np.isfinite(poses).all() or np.any(normalized<0) or np.any(normalized>1):raise ValueError('pose outside fixed support')
    cells=np.minimum((normalized*5).astype(int),4)
    return (cells[:,0]*25+cells[:,1]*5+cells[:,2]).tolist()


def run():
    path=AI/'eval/scene_split_audit_v0_plan.json';plan=json.loads(path.read_text())
    for f,h in plan['file_sha256'].items():
        if hashlib.sha256((ROOT/f).read_bytes()).hexdigest()!=h:raise ValueError('source changed: '+f)
    out=AI/'eval/scene_split_audit_v0_report.json'
    if out.exists():raise FileExistsError(out)
    catalog=catalog_for_workspace(ROOT);cohorts={};all_pixels={}
    for name,spec in plan['cohorts'].items():
        start,count=spec['groups'];rows=[];geometry=[];pixel_digest=hashlib.sha256()
        for seed in range(start,start+count):
            group_pose=None
            for condition in plan['conditions']:
                image,label,mask=render_controlled(seed,catalog,condition,spec['style']);image,_=normalize(image)
                rgb=np.asarray(image.resize((128,96))).transpose(2,0,1).copy();pixel_digest.update(rgb.tobytes());digest=hashlib.sha256(rgb.tobytes()).hexdigest()
                if group_pose is None:group_pose=label['pose']
                else:assert group_pose==label['pose']
                rows.append(dict(seed=seed,condition=condition,pose=label['pose'],pixels_sha256=digest,mean_rgb=float(rgb.mean()),foreground_board_fraction=float((np.asarray(mask)>0).mean())))
                all_pixels.setdefault(digest,[]).append([name,seed,condition])
            geometry.append(group_pose)
        original=json.loads((ROOT/spec['evidence']).read_text())
        expected=original['splits'][name]['pixels_sha256'] if name in ('training','development') else original['pixels_sha256']
        assert pixel_digest.hexdigest()==expected
        bins=pose_bins(geometry);counts=np.bincount(bins,minlength=125)
        cohorts[name]=dict(groups=count,images=len(rows),style=spec['style'],pixels_sha256=pixel_digest.hexdigest(),rows=rows,
            pose_bin_counts=counts.tolist(),occupied_pose_bins=int((counts>0).sum()),pose_min=np.min(geometry,axis=0).tolist(),pose_max=np.max(geometry,axis=0).tolist(),
            condition_summary={c:dict(images=sum(r['condition']==c for r in rows),mean_rgb=float(np.mean([r['mean_rgb'] for r in rows if r['condition']==c])),mean_foreground_board_fraction=float(np.mean([r['foreground_board_fraction'] for r in rows if r['condition']==c]))) for c in plan['conditions']})
    names=list(cohorts);overlap={}
    for i,a in enumerate(names):
        for b in names[i+1:]:overlap[a+'__'+b]=sorted({r['seed'] for r in cohorts[a]['rows']}&{r['seed'] for r in cohorts[b]['rows']})
    duplicate_cross=[v for v in all_pixels.values() if len({r[0] for r in v})>1]
    training=cohorts['training'];train_poses=np.array([r['pose'] for r in training['rows'][::4]])
    for name in ['development','consumed_evaluation']:
        poses=np.array([r['pose'] for r in cohorts[name]['rows'][::4]])
        distances=np.sqrt((((poses[:,None,:]-train_poses[None,:,:])/np.array([30.,24.,.2]))**2).sum(2)).min(1)
        cohorts[name]['training_coverage']=dict(groups_in_empty_training_bins=sum(training['pose_bin_counts'][b]==0 for b in pose_bins(poses)),
            nearest_normalized_pose_distance_median=float(np.median(distances)),nearest_normalized_pose_distance_p95=float(np.percentile(distances,95)),
            outside_training_axis_range=np.sum((poses<train_poses.min(0))|(poses>train_poses.max(0)),axis=0).tolist())
    start,count=plan['cohorts']['training']['groups'];folds=group_folds(range(start,start+count))
    result=dict(plan_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),cohorts=cohorts,scene_overlap=overlap,cross_cohort_exact_pixel_duplicates=duplicate_cross,
        validation_scene_folds=folds,fold_corner_counts=[[sum(seed%4==c for seed in fold) for c in range(4)] for fold in folds],
        new_fits=0,hardware_writes=0,physical_movements=0,qualification_installed=False,
        limitations=['Audits only three named recent cohorts, not the complete historical pretraining corpus',
        'No exact duplicate is not proof against semantic or near-duplicate leakage',
        'Pose bins, RGB and foreground summaries are descriptive and cannot establish cause of generalization failure',
        '15M development and30M consumed evaluation are excluded from future model-selection folds',
        'Fixed baseline was historically selected on15M development; grouped29M validation is conditional on that prior model selection',
        'No images beyond previously consumed cohorts generated'])
    out.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    print(json.dumps(dict(overlap=overlap,pixel_duplicates=len(duplicate_cross),coverage={n:{k:v for k,v in c.items() if k in ['groups','images','style','occupied_pose_bins','training_coverage']} for n,c in cohorts.items()},fold_sizes=[len(f) for f in folds],corner_counts=result['fold_corner_counts']),indent=2))
if __name__=='__main__':run()
