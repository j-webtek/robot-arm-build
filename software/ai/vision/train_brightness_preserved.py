"""Matched augmentation with frozen-teacher preservation on original images; development only."""
import hashlib,json,math,sys
from pathlib import Path
AI_DIR=Path(__file__).resolve().parents[1];ROOT=AI_DIR.parents[1]
sys.path[:0]=[str(AI_DIR),str(AI_DIR.parent/'src')]
import numpy as np
import torch
from PIL import ImageEnhance
from vision.pose_model import KeyboardPoseNet
from vision.synthetic_keyboard import render,catalog_for_workspace,PHOTO_STUDY_CENTER_MM
from vision.evaluate_pose_challenge import _alter


def use_dark_copy(seed, training_start, augment):
    """Darken the extra copy for exactly half the training seed groups."""
    return augment and (seed-training_start) % 2 == 0


def preservation_loss(prediction, teacher, mask):
    """Mean weighted normalized pose loss on original images only."""
    per_image=((prediction-teacher).square()*prediction.new_tensor([4,4,1])).sum(dim=1)/9
    return (per_image*mask).sum()/mask.sum().clamp_min(1)


def train(plan_path, output, preservation_weight):
    augment=True
    weights=[4,4,1]
    size=[128,96]
    if output.exists(): raise ValueError('Use a new output directory')
    plan=json.loads(plan_path.read_text())
    for relative,digest in plan['file_sha256'].items():
        if hashlib.sha256((ROOT/relative).read_bytes()).hexdigest()!=digest: raise ValueError('Frozen source changed')
    checkpoint=ROOT/plan['initial_checkpoint']
    if hashlib.sha256(checkpoint.read_bytes()).hexdigest()!=plan['initial_checkpoint_sha256']: raise ValueError('Initial checkpoint changed')
    torch.manual_seed(plan['training_seed']);torch.set_num_threads(4)
    catalog=catalog_for_workspace(ROOT)
    if catalog.content_sha256!=plan['target_catalog_sha256']: raise ValueError('Catalog changed')
    def samples(split):
        pixels=[];labels=[];original=[]
        start,count=plan[split]
        for seed in range(start,start+count):
            conditions=plan['conditions'] if split=='training_groups' else plan['evaluation_conditions']
            for condition in conditions:
                image,pose=render(seed,catalog,domain='appearance_shift' if condition=='appearance_shift' else 'standard')
                if condition=='challenge': image=_alter(image,seed)
                image=image.resize(tuple(size))
                if condition=='darkened_standard': image=ImageEnhance.Brightness(image).enhance(plan['brightness_factor'])
                variants=[image]
                if split=='training_groups':
                    variants.append(ImageEnhance.Brightness(image).enhance(plan['brightness_factor']) if use_dark_copy(seed,start,augment) else image.copy())
                for variant_index,variant in enumerate(variants):
                    original.append(not (split=="training_groups" and variant_index==1 and use_dark_copy(seed,start,augment)))
                    pixels.append(np.asarray(variant,dtype=np.uint8).transpose(2,0,1).copy())
                    labels.append(((pose[0]-PHOTO_STUDY_CENTER_MM[0])/30,(pose[1]-PHOTO_STUDY_CENTER_MM[1])/24,(pose[2]-math.pi)/.2))
        return torch.from_numpy(np.stack(pixels)),torch.tensor(labels,dtype=torch.float32),torch.tensor(original,dtype=torch.float32)
    train_x,train_y,original_mask=samples('training_groups');dev_x,dev_y,_=samples('development_groups')
    device='cuda' if torch.cuda.is_available() else 'cpu'
    model=KeyboardPoseNet().to(device);model.load_state_dict(torch.load(checkpoint,map_location=device,weights_only=True))
    model.eval()
    with torch.no_grad():
        teacher_predictions=torch.cat([model(batch.to(device).float()/255).cpu() for batch in train_x.split(64)])
    optimizer=torch.optim.AdamW(model.parameters(),lr=plan['learning_rate'],weight_decay=.0001)
    loader=torch.utils.data.DataLoader(torch.utils.data.TensorDataset(train_x,train_y,teacher_predictions,original_mask),batch_size=64,shuffle=True,
        generator=torch.Generator().manual_seed(plan['training_seed']))
    output.mkdir(parents=True)
    best=float('inf');history=[];selected=0
    for epoch in range(plan['epochs']):
        model.train();total=0
        for x,y,teacher,mask in loader:
            optimizer.zero_grad(set_to_none=True)
            prediction=model(x.to(device).float()/255)
            residual=prediction-y.to(device)
            loss=(residual.square()*torch.tensor(weights,device=device)).sum(dim=1).mean()/sum(weights)
            loss=loss+preservation_weight*preservation_loss(prediction,teacher.to(device),mask.to(device))
            loss.backward();optimizer.step()
            total+=float(loss.detach())*len(x)
        model.eval()
        with torch.no_grad():
            prediction=torch.cat([model(batch.to(device).float()/255).cpu() for batch in dev_x.split(64)])
            dev_loss=float(torch.nn.functional.mse_loss(prediction,dev_y))
        if dev_loss<best:
            best=dev_loss;selected=epoch+1
            torch.save({k:v.detach().cpu() for k,v in model.state_dict().items()},output/'pose_model.pt')
        history.append({'epoch':epoch+1,'training_objective':total/len(train_x),'development_mse':dev_loss})
        print(history[-1],flush=True)
    model.load_state_dict(torch.load(output/'pose_model.pt',map_location=device,weights_only=True));model.eval()
    with torch.no_grad():
        prediction=torch.cat([model(batch.to(device).float()/255).cpu() for batch in dev_x.split(64)])
    from vision.train_pose import _pose_from_prediction
    from vision.synthetic_keyboard import transform_target
    errors=[];group_max=[];centers=[];yaws=[];cases=[]
    for row,truth_row in zip(prediction,dev_y):
        predicted_pose=_pose_from_prediction(row);truth_pose=_pose_from_prediction(truth_row)
        centers.append(math.dist(predicted_pose[:2],truth_pose[:2]))
        yaws.append(abs(math.degrees(predicted_pose[2]-truth_pose[2])))
        local=[]
        for region in catalog.keyboard_targets.values():
            a=transform_target(region.center.x,region.center.y,predicted_pose[:2],predicted_pose[2])
            b=transform_target(region.center.x,region.center.y,truth_pose[:2],truth_pose[2])
            local.append(math.dist(a,b))
        errors.extend(local);group_max.append(max(local))
        index=len(cases)
        cases.append(dict(seed=plan['development_groups'][0]+index//len(plan['evaluation_conditions']),
            condition=plan['evaluation_conditions'][index%len(plan['evaluation_conditions'])],
            mean_mm=float(np.mean(local)),maximum_mm=max(local),center_mm=centers[-1],yaw_degrees=yaws[-1],
            within_1mm_count=sum(e<=1 for e in local)))
    result=dict(scope='DEVELOPMENT_ONLY',input_size=size,loss_weights=weights,selected_epoch=selected,
        center_mean_mm=float(np.mean(centers)),yaw_mean_degrees=float(np.mean(yaws)),yaw_p95_degrees=float(np.percentile(yaws,95)),
        mean_mm=float(np.mean(errors)),p95_mm=float(np.percentile(errors,95)),maximum_mm=max(errors),
        within_1mm_fraction=sum(e<=1 for e in errors)/len(errors),target_view_count=len(errors),
        worst_image_error_p95_mm=float(np.percentile(group_max,95)),
        checkpoint_sha256=hashlib.sha256((output/'pose_model.pt').read_bytes()).hexdigest(),
        history=history,device=device,training_images=len(train_x),development_images=len(dev_x),
        training_pixels_sha256=hashlib.sha256(train_x.numpy().tobytes()).hexdigest(),
        development_pixels_sha256=hashlib.sha256(dev_x.numpy().tobytes()).hexdigest(),
        qualification_installed=False,hardware_writes=0,physical_movements=0)
    result['preservation_weight']=preservation_weight
    result['teacher_predictions_sha256']=hashlib.sha256(teacher_predictions.numpy().tobytes()).hexdigest()
    result['original_training_images']=int(original_mask.sum())
    result['augmentation']=augment
    result['darkened_training_images']=plan['training_groups'][1]//2*len(plan['conditions']) if augment else 0
    result['by_condition']={}
    for condition in plan['evaluation_conditions']:
        rows=[r for r in cases if r['condition']==condition]
        result['by_condition'][condition]=dict(images=len(rows),mean_mm=float(np.mean([r['mean_mm'] for r in rows])),
            center_mean_mm=float(np.mean([r['center_mm'] for r in rows])),
            yaw_p95_degrees=float(np.percentile([r['yaw_degrees'] for r in rows],95)),
            above_3mm_images=sum(r['maximum_mm']>3 for r in rows),
            within_1mm_fraction=sum(r['within_1mm_count'] for r in rows)/(len(rows)*len(catalog.keyboard_targets)))
    result['cases']=cases
    (output/'training_result.json').write_bytes((json.dumps(result,indent=2)+'\n').encode())
    return result


if __name__=='__main__':
    plan_path=AI_DIR/'train/brightness_preserved_v0_plan.json'
    plan=json.loads(plan_path.read_text())
    results=[]
    for name,preservation_weight in plan['arms'].items():
        results.append(train(plan_path,AI_DIR/'results'/('brightness_preserved_v0_'+name),preservation_weight))
    report=dict(scope='DEVELOPMENT_ONLY',plan_sha256=hashlib.sha256(plan_path.read_bytes()).hexdigest(),
        results=results,hardware_writes=0,physical_movements=0,qualification_installed=False,
        limitations=['Both arms use same 128x96 starting checkpoint, sample order, budget and unweighted development-MSE epoch selection',
                    'Epoch selected on development MSE; development metrics are optimistic selection evidence',
                    'Renderer remains 256x192; no real camera or held-out evaluation data',
                    'One training seed per arm; no claim of statistical significance'])
    control,candidate=results
    checks={}
    for condition in plan['evaluation_conditions']:
        a=control['by_condition'][condition];b=candidate['by_condition'][condition]
        checks[condition]=dict(mean_error=b['mean_mm']<a['mean_mm'] if condition=='darkened_standard' else b['mean_mm']<=a['mean_mm']*1.05,
            yaw=b['yaw_p95_degrees']<=a['yaw_p95_degrees']*1.10,
            tail=b['above_3mm_images']<a['above_3mm_images'] if condition=='darkened_standard' else b['above_3mm_images']<=a['above_3mm_images'])
    report['development_checks']=checks
    reference=json.loads((ROOT/plan['reference_scorecard']).read_text())['results'][0]
    reference_checks={}
    for condition in plan['evaluation_conditions']:
        a=reference['by_condition'][condition];b=candidate['by_condition'][condition]
        reference_checks[condition]=dict(mean_error=b['mean_mm']<a['mean_mm'] if condition=='darkened_standard' else b['mean_mm']<=a['mean_mm']*1.05,
            yaw=b['yaw_p95_degrees']<=a['yaw_p95_degrees']*1.10,
            tail=b['above_3mm_images']<a['above_3mm_images'] if condition=='darkened_standard' else b['above_3mm_images']<=a['above_3mm_images'])
    report['reference_checks']=reference_checks
    report['development_rule_passed']=all(all(c.values()) for c in list(checks.values())+list(reference_checks.values()))
    report['limitations'].append('Fixed brightness 0.5 is reused from diagnostic; paired development selection only; both arms use identical 25-percent dark augmentation and learning rate0.00005; candidate adds teacher preservation weight4 on original images; frozen nonaugmented reference gates also required')
    (AI_DIR/'eval/brightness_preserved_v0_scorecard.json').write_bytes((json.dumps(report,indent=2)+'\n').encode())
    print([(r['loss_weights'],r['mean_mm'],r['within_1mm_fraction']) for r in results],flush=True)
