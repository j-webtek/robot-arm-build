"""Train localized obstruction risk and test the unchanged combined scale."""
import hashlib,json,sys
from pathlib import Path
AI=Path(__file__).resolve().parents[1];ROOT=AI.parents[1];sys.path[:0]=[str(AI),str(AI.parent/'src')]
import numpy as np
import torch
from train.train_obstruction_risk_scale import raw_set,probabilities,checks,passed
from vision.audit_scale_ranking import auc
from vision.diverse_pose_models import MODELS
from vision.evaluate_ensemble_scaled_uncertainty import infer_cohort,summarize
from vision.evaluate_grouped_uncertainty import calibrate
from vision.linear_residual_pose import LinearResidualPoseNet
from vision.multiscale_obstruction_model import MultiScaleObstructionNet
from vision.synthetic_keyboard import catalog_for_workspace


def run():
    path=AI/'train/multiscale_obstruction_scale_v1_plan.json';plan=json.loads(path.read_text())
    for name,digest in plan['file_sha256'].items():
        if hashlib.sha256((ROOT/name).read_bytes()).hexdigest()!=digest:raise ValueError('source mismatch: '+name)
    output=AI/'eval/multiscale_obstruction_scale_v1_report.json';directory=AI/'results/multiscale_obstruction_scale_v1'
    if output.exists() or directory.exists():raise FileExistsError('existing multiscale evidence')
    torch.set_num_threads(4);device='cuda' if torch.cuda.is_available() else 'cpu';catalog=catalog_for_workspace(ROOT);targets=list(catalog.keyboard_targets.values())
    train_pixels,train_labels,metadata=raw_set(*plan['groups']['training'],plan,catalog);sample_weights=np.asarray([plan['condition_loss_weights'][c] for _,_,c in metadata],dtype=np.float32)
    torch.manual_seed(plan['seed']);model=MultiScaleObstructionNet().to(device)
    loader=torch.utils.data.DataLoader(torch.utils.data.TensorDataset(torch.from_numpy(train_pixels),torch.from_numpy(train_labels),torch.from_numpy(sample_weights)),batch_size=plan['batch_size'],shuffle=True,generator=torch.Generator().manual_seed(plan['seed']))
    optimizer=torch.optim.AdamW(model.parameters(),lr=plan['learning_rate'],weight_decay=plan['weight_decay']);history=[]
    for epoch in range(plan['epochs']):
        model.train();total=weight_total=0.
        for images,truth,weight in loader:
            optimizer.zero_grad(set_to_none=True);per=torch.nn.functional.binary_cross_entropy_with_logits(model(images.to(device).float()/255),truth.to(device),reduction='none');weight=weight.to(device);loss=(per*weight).sum()/weight.sum();loss.backward();optimizer.step();total+=float((per.detach()*weight).sum());weight_total+=float(weight.sum())
        history.append(dict(epoch=epoch+1,weighted_training_loss=total/weight_total));print(history[-1],flush=True)
    directory.mkdir();checkpoint=directory/'model.pt';torch.save({k:v.detach().cpu() for k,v in model.state_dict().items()},checkpoint)
    pose_models={'candidate':LinearResidualPoseNet.from_export(torch.load(ROOT/plan['candidate_artifact'],weights_only=True,map_location='cpu')).to(device)}
    for name,checkpoint_path in plan['selected_checkpoints'].items():
        member=MODELS[name]().to(device);member.load_state_dict(torch.load(ROOT/checkpoint_path,weights_only=True,map_location=device));pose_models[name]=member
    cohorts={}
    for cohort in ['mapping_calibration','selection']:
        group=plan['groups'][cohort];base=infer_cohort(plan,group,pose_models,catalog,targets,device);raw,labels,order=raw_set(*group,plan,catalog);probs=probabilities(model,raw,device,plan['batch_size'])
        if order!=[(r['seed'],r['style'],r['condition']) for r in base['rows']]:raise ValueError('row order mismatch')
        rows=[dict(row,obstruction_probability=float(prob),scale_mm=max(row['disagreement_mm'],plan['scale_floor_mm'])*(1+plan['obstruction_multiplier']*float(prob))) for row,prob in zip(base['rows'],probs)]
        cohorts[cohort]=dict(rows=rows,raw_pixels_sha256=hashlib.sha256(raw.tobytes()).hexdigest(),normalized_pixels_sha256=base['pixels_sha256'],prediction_sha256=base['prediction_sha256'],obstruction_prediction_sha256=hashlib.sha256(probs.tobytes()).hexdigest(),labels_sha256=hashlib.sha256(labels.tobytes()).hexdigest())
        if cohort=='selection':
            predicted=probs>=.5;positive=labels==1;classifier=dict(auc=auc(probs,labels*4),accuracy=float((predicted==positive).mean()),obstruction_recall=float(predicted[positive].mean()),clean_false_positive=float(predicted[~positive].mean()))
    start,count=plan['groups']['mapping_calibration'];calrows=cohorts['mapping_calibration']['rows'];scene_scores=[dict(seed=seed,normalized_max=max(r['error_mm']/r['scale_mm'] for r in calrows if r['seed']==seed)) for seed in range(start,start+count)];rank,q=calibrate([r['normalized_max'] for r in scene_scores],plan['alpha']);cohorts['mapping_calibration']['scene_scores']=scene_scores
    rows=cohorts['selection']['rows'];summary=summarize(rows,q,plan['tolerance_mm']);conditions={c:summarize([r for r in rows if r['condition']==c],q,plan['tolerance_mm']) for c in plan['conditions']};decision=checks(summary,conditions,classifier,plan);ok=passed(decision)
    result=dict(plan_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),prior_report_sha256=plan['file_sha256'][plan['prior_report']],device=device,model_parameters=sum(p.numel() for p in MultiScaleObstructionNet().parameters()),checkpoint_sha256=hashlib.sha256(checkpoint.read_bytes()).hexdigest(),training_pixels_sha256=hashlib.sha256(train_pixels.tobytes()).hexdigest(),training_labels_sha256=hashlib.sha256(train_labels.tobytes()).hexdigest(),training_weights_sha256=hashlib.sha256(sample_weights.tobytes()).hexdigest(),history=history,rank=rank,normalized_quantile=q,cohorts=cohorts,classifier=classifier,selection_summary=summary,selection_conditions=conditions,checks=decision,passed_selection=ok,classifier_fits=1,calibration_fits=1,optimizer_updates=plan['epochs']*int(np.ceil(len(train_pixels)/plan['batch_size'])),hardware_writes=0,physical_movements=0,qualification_installed=False,limitations=['Synthetic training-selection evidence only; no confirmation or physical-camera claim.','Raw-image classifier uses no condition label or mask at inference.','Passing permits only another frozen calibration/confirmation chain.','No runtime installation or motion authority.'])
    output.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n');print(json.dumps(dict(classifier=classifier,rank=rank,normalized_quantile=q,summary=summary,conditions=conditions,checks=decision,passed_selection=ok),indent=2))
if __name__=='__main__':run()
