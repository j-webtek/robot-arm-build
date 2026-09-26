"""Frozen landmark heatmap and visibility diagnosis; no model modification."""
import hashlib,json,sys
from pathlib import Path
AI=Path(__file__).resolve().parents[1];ROOT=AI.parents[1]
sys.path[:0]=[str(AI),str(AI.parent/'src')]
import numpy as np
import torch
from vision.landmark_model import heatmap_coordinates
from vision.temperature_visibility_model import TemperatureVisibilityNet
from vision.landmark_occlusions import render_controlled
from vision.synthetic_keyboard import catalog_for_workspace
from vision.evaluate_dark_only_normalization import normalize


def run():
    path=AI/'eval/corner_attribution_v0.manifest.json';m=json.loads(path.read_text())
    for f,h in m['file_sha256'].items():
        if hashlib.sha256((ROOT/f).read_bytes()).hexdigest()!=h:raise ValueError('frozen source changed')
    ck=ROOT/m['checkpoint']
    if hashlib.sha256(ck.read_bytes()).hexdigest()!=m['checkpoint_sha256']:raise ValueError('checkpoint changed')
    model=TemperatureVisibilityNet("t05");model.load_state_dict(torch.load(ck,map_location='cpu',weights_only=True));model.eval();torch.set_num_threads(4)
    catalog=catalog_for_workspace(ROOT);rows=[];gx=torch.arange(64)[None,:]*4;gy=torch.arange(48)[:,None]*4
    for seed in range(15000000,15000200):
        for condition in m['conditions']:
            image,label,_=render_controlled(seed,catalog,condition,'ellipse');image,_=normalize(image)
            pixels=np.asarray(image,dtype=np.uint8).transpose(2,0,1).copy()
            with torch.no_grad():out=model(torch.from_numpy(pixels)[None].float()/255)
            probability=out['heatmap_logits'][0].flatten(1).softmax(-1).reshape(4,48,64)
            soft=heatmap_coordinates(out['heatmap_logits'])[0];sharp=heatmap_coordinates(out['heatmap_logits']/0.5)[0];vis=out['visibility_logits'][0].sigmoid()
            for i,p in enumerate(label['landmarks']):
                q=probability[i];index=int(q.argmax());peak=torch.tensor([(index%64)*4,(index//64)*4]);truth=torch.tensor([p['x_px'],p['y_px']])
                fraction=p['unoccluded_fraction'];group='hidden' if fraction==0 else 'clear' if fraction==1 else 'partial'
                corners=torch.tensor([[v['x_px'],v['y_px']] for v in label['landmarks']])
                distances=torch.linalg.vector_norm(corners-peak,dim=1);nearest=int(distances.argmin())
                outside=((gx-peak[0])**2+(gy-peak[1])**2)>64
                rival=q.masked_fill(~outside,-1);rival_index=int(rival.argmax())
                rival_point=torch.tensor([(rival_index%64)*4,(rival_index//64)*4])
                rival_distances=torch.linalg.vector_norm(corners-rival_point,dim=1)
                rows.append(dict(nearest_corner=nearest,nearest_distance_px=float(distances[nearest]),
                    rival_ratio=float(rival.max()/q.max()),rival_own_error_px=float(rival_distances[i]),
                    rival_nearest_corner=int(rival_distances.argmin()),
seed=seed,condition=condition,corner=i,visibility_class=group,target_visibility=fraction,predicted_visibility=float(vis[i]),
                    soft_error_px=float(torch.linalg.vector_norm(soft[i]-truth)),sharp_error_px=float(torch.linalg.vector_norm(sharp[i]-truth)),
                    soft_bias_px=(soft[i]-truth).tolist(),sharp_bias_px=(sharp[i]-truth).tolist(),peak_error_px=float(torch.linalg.vector_norm(peak-truth)),
                    peak_probability=float(q.max()),entropy=float(-(q*q.clamp_min(1e-12).log()).sum()),
                    mass_within_8px=float(q[((gx-truth[0])**2+(gy-truth[1])**2)<=64].sum())))
    summaries={}
    for group in ('clear','partial','hidden'):
        selected=[r for r in rows if r['visibility_class']==group]
        large=[r for r in selected if r['peak_error_px']>8]
        summaries[group]=dict(corners=len(selected),large_peak_errors=len(large),
            near_other_corner=sum(r['nearest_corner']!=r['corner'] and r['nearest_distance_px']<=8 for r in large),
            strong_rival=sum(r['rival_ratio']>=.5 for r in large),
            rival_near_correct=sum(r['rival_own_error_px']<=8 for r in large),
            strong_rival_near_correct=sum(r['rival_ratio']>=.5 and r['rival_own_error_px']<=8 for r in large))
    report=dict(manifest_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),rows=rows,summaries=summaries,
        hardware_writes=0,physical_movements=0,qualification_installed=False,
        limitations=['Reused synthetic data, CPU inference, fixed8px radius and0.5 rival ratio are descriptive only',
                    'Nearest-corner association does not establish a semantic swap or causality',
                    'Rival outside8px may be a broad shoulder; no runtime correction or qualification'])
    out=AI/'eval/corner_attribution_v0_report.json'
    if out.exists():raise FileExistsError(out)
    out.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(summaries,indent=2))
if __name__=='__main__':run()
