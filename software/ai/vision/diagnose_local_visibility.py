"""Frozen landmark heatmap and visibility diagnosis; no model modification."""
import hashlib,json,sys
from pathlib import Path
AI=Path(__file__).resolve().parents[1];ROOT=AI.parents[1]
sys.path[:0]=[str(AI),str(AI.parent/'src')]
import numpy as np
import torch
from vision.landmark_model import heatmap_coordinates
from vision.local_visibility_model import LocalVisibilityNet
from vision.diagnose_landmark_visibility_response import summarize
from vision.landmark_occlusions import render_controlled
from vision.synthetic_keyboard import catalog_for_workspace
from vision.evaluate_dark_only_normalization import normalize


def run():
    path=AI/'eval/local_visibility_diagnostic_v0.manifest.json';m=json.loads(path.read_text())
    for f,h in m['file_sha256'].items():
        if hashlib.sha256((ROOT/f).read_bytes()).hexdigest()!=h:raise ValueError('frozen source changed')
    ck=ROOT/m['checkpoint']
    if hashlib.sha256(ck.read_bytes()).hexdigest()!=m['checkpoint_sha256']:raise ValueError('checkpoint changed')
    model=LocalVisibilityNet("local");model.load_state_dict(torch.load(ck,map_location='cpu',weights_only=True));model.eval();torch.set_num_threads(4)
    catalog=catalog_for_workspace(ROOT);rows=[];gx=torch.arange(64)[None,:]*4;gy=torch.arange(48)[:,None]*4
    for seed in range(15000000,15000200):
        for condition in m['conditions']:
            image,label,_=render_controlled(seed,catalog,condition,'ellipse');image,_=normalize(image)
            pixels=np.asarray(image,dtype=np.uint8).transpose(2,0,1).copy()
            with torch.no_grad():out=model(torch.from_numpy(pixels)[None].float()/255)
            probability=out['heatmap_logits'][0].flatten(1).softmax(-1).reshape(4,48,64)
            soft=heatmap_coordinates(out['heatmap_logits'])[0];vis=out['visibility_logits'][0].sigmoid()
            for i,p in enumerate(label['landmarks']):
                q=probability[i];index=int(q.argmax());peak=torch.tensor([(index%64)*4,(index//64)*4]);truth=torch.tensor([p['x_px'],p['y_px']])
                fraction=p['unoccluded_fraction'];group='hidden' if fraction==0 else 'clear' if fraction==1 else 'partial'
                rows.append(dict(seed=seed,condition=condition,corner=i,visibility_class=group,target_visibility=fraction,predicted_visibility=float(vis[i]),
                    soft_error_px=float(torch.linalg.vector_norm(soft[i]-truth)),peak_error_px=float(torch.linalg.vector_norm(peak-truth)),
                    peak_probability=float(q.max()),entropy=float(-(q*q.clamp_min(1e-12).log()).sum()),
                    mass_within_8px=float(q[((gx-truth[0])**2+(gy-truth[1])**2)<=64].sum())))
    summaries={}
    for group in ('clear','partial','hidden'):
        selected=[r for r in rows if r['visibility_class']==group]
        summaries[group]=dict(corners=len(selected),soft_mean_px=float(np.mean([r['soft_error_px'] for r in selected])),
            peak_mean_px=float(np.mean([r['peak_error_px'] for r in selected])),peak_p95_px=float(np.percentile([r['peak_error_px'] for r in selected],95)),
            predicted_visibility_mean=float(np.mean([r['predicted_visibility'] for r in selected])),predicted_visible=sum(r['predicted_visibility']>=.5 for r in selected),
            mass_within_8px_mean=float(np.mean([r['mass_within_8px'] for r in selected])),entropy_mean=float(np.mean([r['entropy'] for r in selected])))
    training=json.loads((AI/'eval/landmark_local_visibility_v0_local_scorecard.json').read_text())
    strata={}
    for group in ('clear','partial','hidden'):
        strata[group]={}
        for lo,hi in ((0,4),(4,8),(8,float('inf'))):
            selected=[r for r in rows if r['visibility_class']==group and lo<=r['peak_error_px']<hi]
            strata[group][str(lo)+'_'+str(hi)]=dict(corners=len(selected),predicted_visible=sum(r['predicted_visibility']>=.5 for r in selected))
    paired={}
    for mode in ('global','local'):
        source=AI/f'eval/landmark_local_visibility_v0_{mode}_scorecard.json'
        paired[mode]=summarize(json.loads(source.read_text())['cases'])
    report=dict(strata=strata,paired=paired,scope='RETAINED_DEVELOPMENT_DIAGNOSTIC',manifest_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),rows=rows,summaries=summaries,
        training_selected_epoch=training['selected_epoch'],hardware_writes=0,physical_movements=0,qualification_installed=False,
        limitations=['Reused development data, no retraining or new held-out evidence',
                    'Peak decoding diagnostic only; no estimator promotion or calibrated visibility',
                    'Visibility imbalance and diffuse heatmaps are associations, not proof of a single cause'])
    out=AI/'eval/local_visibility_diagnostic_v0_report.json'
    if out.exists():raise FileExistsError(out)
    out.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(summaries=summaries,strata=strata,paired={k:{a:b for a,b in v.items() if a!="rows"} for k,v in paired.items()}),indent=2))


if __name__=='__main__':run()
