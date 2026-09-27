"""Train an image-only obstruction signal and test one frozen combined scale."""

import hashlib,json,sys
from pathlib import Path
AI=Path(__file__).resolve().parents[1];ROOT=AI.parents[1];sys.path[:0]=[str(AI),str(AI.parent/'src')]
import numpy as np
import torch
from vision.audit_scale_ranking import auc
from vision.diverse_pose_models import MODELS
from vision.evaluate_ensemble_scaled_uncertainty import infer_cohort,summarize
from vision.evaluate_grouped_uncertainty import calibrate
from vision.landmark_occlusions import render_controlled
from vision.linear_residual_pose import LinearResidualPoseNet
from vision.obstruction_risk_model import ObstructionRiskNet
from vision.synthetic_keyboard import catalog_for_workspace


def raw_set(start,count,plan,catalog):
    pixels=[];labels=[];metadata=[]
    for seed in range(start,start+count):
        for style in plan['styles']:
            for condition in plan['conditions']:
                image,_,_=render_controlled(seed,catalog,condition,style)
                pixels.append(np.asarray(image.resize((128,96))).transpose(2,0,1).copy())
                labels.append(float(condition in ('partial','full')))
                metadata.append((seed,style,condition))
    return np.stack(pixels),np.asarray(labels,dtype=np.float32),metadata


def probabilities(model,pixels,device,batch_size):
    model.eval();values=[]
    with torch.no_grad():
        for batch in torch.from_numpy(pixels).split(batch_size):
            values.append(torch.sigmoid(model(batch.to(device).float()/255)).cpu().numpy())
    return np.concatenate(values)


def checks(summary,conditions,classifier,plan):
    return dict(
        classifier_auc=classifier['auc']>=plan['minimum_classifier_auc'],
        classifier_obstruction_recall=classifier['obstruction_recall']>=plan['minimum_obstruction_recall'],
        classifier_clean_false_positive=classifier['clean_false_positive']<=plan['maximum_clean_false_positive'],
        overall_scene_coverage=summary['scene_coverage']>=plan['minimum_scene_coverage'],
        overall_accepted_fraction=summary['accepted_fraction']>=plan['minimum_accepted_fraction'],
        overall_accepted_image_coverage=summary['accepted_image_coverage'] is not None and summary['accepted_image_coverage']>=plan['minimum_accepted_image_coverage'],
        overall_accepted_scene_coverage=summary['accepted_scene_coverage'] is not None and summary['accepted_scene_coverage']>=plan['minimum_accepted_scene_coverage'],
        zero_accepted_errors_over_tolerance=summary['accepted_errors_over_tolerance']==0,
        condition_accepted_fraction={c:v['accepted_fraction']>=plan['minimum_condition_accepted_fraction'] for c,v in conditions.items()},
        condition_accepted_image_coverage={c:v['accepted_image_coverage'] is not None and v['accepted_image_coverage']>=plan['minimum_accepted_image_coverage'] for c,v in conditions.items()})


def passed(value):
    return all(v for v in value.values() if isinstance(v,bool)) and all(value['condition_accepted_fraction'].values()) and all(value['condition_accepted_image_coverage'].values())


def run():
    path=AI/'train/obstruction_risk_scale_v1_plan.json';plan=json.loads(path.read_text())
    for name,digest in plan['file_sha256'].items():
        if hashlib.sha256((ROOT/name).read_bytes()).hexdigest()!=digest:raise ValueError('source mismatch: '+name)
    output=AI/'eval/obstruction_risk_scale_v1_report.json';directory=AI/'results/obstruction_risk_scale_v1'
    if output.exists() or directory.exists():raise FileExistsError('existing obstruction-risk evidence')
    torch.set_num_threads(4);device='cuda' if torch.cuda.is_available() else 'cpu';catalog=catalog_for_workspace(ROOT);targets=list(catalog.keyboard_targets.values())
    train_pixels,train_labels,_=raw_set(*plan['groups']['training'],plan,catalog)
    torch.manual_seed(plan['seed']);model=ObstructionRiskNet().to(device)
    loader=torch.utils.data.DataLoader(torch.utils.data.TensorDataset(torch.from_numpy(train_pixels),torch.from_numpy(train_labels)),batch_size=plan['batch_size'],shuffle=True,generator=torch.Generator().manual_seed(plan['seed']))
    optimizer=torch.optim.AdamW(model.parameters(),lr=plan['learning_rate'],weight_decay=plan['weight_decay']);history=[]
    for epoch in range(plan['epochs']):
        model.train();total=0.
        for images,truth in loader:
            optimizer.zero_grad(set_to_none=True);loss=torch.nn.functional.binary_cross_entropy_with_logits(model(images.to(device).float()/255),truth.to(device));loss.backward();optimizer.step();total+=float(loss.detach())*len(images)
        history.append(dict(epoch=epoch+1,training_loss=total/len(train_pixels)));print(history[-1],flush=True)
    directory.mkdir();checkpoint=directory/'model.pt';torch.save({k:v.detach().cpu() for k,v in model.state_dict().items()},checkpoint)
    pose_models={'candidate':LinearResidualPoseNet.from_export(torch.load(ROOT/plan['candidate_artifact'],weights_only=True,map_location='cpu')).to(device)}
    for name,checkpoint_path in plan['selected_checkpoints'].items():
        member=MODELS[name]().to(device);member.load_state_dict(torch.load(ROOT/checkpoint_path,weights_only=True,map_location=device));pose_models[name]=member
    cohorts={}
    for cohort in ['mapping_calibration','selection']:
        group=plan['groups'][cohort];base=infer_cohort(plan,group,pose_models,catalog,targets,device);raw,labels,metadata=raw_set(*group,plan,catalog);probs=probabilities(model,raw,device,plan['batch_size'])
        if metadata!=[(r['seed'],r['style'],r['condition']) for r in base['rows']]:raise ValueError('row order mismatch')
        rows=[dict(row,obstruction_probability=float(prob),scale_mm=max(row['disagreement_mm'],plan['scale_floor_mm'])*(1+plan['obstruction_multiplier']*float(prob))) for row,prob in zip(base['rows'],probs)]
        cohorts[cohort]=dict(rows=rows,raw_pixels_sha256=hashlib.sha256(raw.tobytes()).hexdigest(),normalized_pixels_sha256=base['pixels_sha256'],prediction_sha256=base['prediction_sha256'],obstruction_prediction_sha256=hashlib.sha256(probs.tobytes()).hexdigest(),labels_sha256=hashlib.sha256(labels.tobytes()).hexdigest())
        if cohort=='selection':
            predicted=probs>=.5;positive=labels==1;classifier=dict(auc=auc(probs,labels*4),accuracy=float((predicted==positive).mean()),obstruction_recall=float(predicted[positive].mean()),clean_false_positive=float(predicted[~positive].mean()))
    start,count=plan['groups']['mapping_calibration'];calrows=cohorts['mapping_calibration']['rows'];scene_scores=[dict(seed=seed,normalized_max=max(r['error_mm']/r['scale_mm'] for r in calrows if r['seed']==seed)) for seed in range(start,start+count)];rank,q=calibrate([r['normalized_max'] for r in scene_scores],plan['alpha']);cohorts['mapping_calibration']['scene_scores']=scene_scores
    rows=cohorts['selection']['rows'];summary=summarize(rows,q,plan['tolerance_mm']);conditions={c:summarize([r for r in rows if r['condition']==c],q,plan['tolerance_mm']) for c in plan['conditions']};decision=checks(summary,conditions,classifier,plan);ok=passed(decision)
    result=dict(plan_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),failed_mapping_report_sha256=plan['file_sha256'][plan['failed_mapping_report']],device=device,model_parameters=sum(p.numel() for p in ObstructionRiskNet().parameters()),checkpoint_sha256=hashlib.sha256(checkpoint.read_bytes()).hexdigest(),training_pixels_sha256=hashlib.sha256(train_pixels.tobytes()).hexdigest(),training_labels_sha256=hashlib.sha256(train_labels.tobytes()).hexdigest(),history=history,rank=rank,normalized_quantile=q,cohorts=cohorts,classifier=classifier,selection_summary=summary,selection_conditions=conditions,checks=decision,passed_selection=ok,classifier_fits=1,calibration_fits=1,optimizer_updates=plan['epochs']*int(np.ceil(len(train_pixels)/plan['batch_size'])),hardware_writes=0,physical_movements=0,qualification_installed=False,limitations=['Synthetic training-selection evidence only; no fresh confirmation or physical-camera claim.','Image-only classifier uses no condition label or mask at inference.','Passing would permit only another frozen calibration/confirmation chain.','No runtime installation or motion authority.'])
    output.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n');print(json.dumps(dict(classifier=classifier,rank=rank,normalized_quantile=q,summary=summary,conditions=conditions,checks=decision,passed_selection=ok),indent=2))
if __name__=='__main__':run()
