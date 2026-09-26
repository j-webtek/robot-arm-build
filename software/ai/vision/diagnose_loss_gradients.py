import hashlib,json,sys,itertools
from pathlib import Path
AI=Path(__file__).resolve().parents[1];ROOT=AI.parents[1];sys.path[:0]=[str(AI),str(AI.parent/'src')]
import numpy as np
import torch
from vision.temperature_visibility_model import TemperatureVisibilityNet
from vision.landmark_model import heatmap_coordinates
from vision.landmark_occlusions import render_controlled
from vision.synthetic_keyboard import catalog_for_workspace
from vision.evaluate_dark_only_normalization import normalize
from train.geometry_auxiliary import geometry_loss
from train.train_geometry_auxiliary import balanced_visibility_loss

def terms(out,points,v):
    gx=torch.arange(64)[None,None,None,:];gy=torch.arange(48)[None,None,:,None]
    t=torch.exp(-((gx-points[:,:,0,None,None]/4)**2+(gy-points[:,:,1,None,None]/4)**2)/(2*1.5**2));t/=t.sum((2,3),keepdim=True).clamp_min(1e-8)
    ce=-(t.flatten(2)*out['heatmap_logits'].flatten(2).log_softmax(-1)).sum(-1)
    coords=heatmap_coordinates(out['heatmap_logits'])
    return dict(heatmap=(ce*v).sum()/v.sum().clamp_min(1),coordinate=((((coords-points)/16).square().sum(-1))*v).sum()/v.sum().clamp_min(1),visibility=balanced_visibility_loss(out['visibility_logits'],v),geometry=geometry_loss(coords,points,v))

def run():
    p=AI/'eval/gradient_diagnostic_v0_plan.json';m=json.loads(p.read_text())
    for f,h in m['file_sha256'].items():assert hashlib.sha256((ROOT/f).read_bytes()).hexdigest()==h
    torch.set_num_threads(4);catalog=catalog_for_workspace(ROOT);batches=[]
    for start in m['batch_starts']:
        pixels=[];points=[];visible=[]
        for seed in range(start,start+8):
            for condition in m['conditions']:
                im,label,_=render_controlled(seed,catalog,condition,'rectangle');im,_=normalize(im)
                pixels.append(np.asarray(im).transpose(2,0,1).copy());points.append([[v['x_px'],v['y_px']] for v in label['landmarks']]);visible.append([v['unoccluded_fraction'] for v in label['landmarks']])
        x=np.stack(pixels);batches.append((torch.from_numpy(x).float()/255,torch.tensor(points),torch.tensor(visible),hashlib.sha256(x.tobytes()).hexdigest()))
    rows=[]
    for state in ('initial','control','geometry'):
        torch.manual_seed(260926);model=TemperatureVisibilityNet('t05');model.eval()
        if state!='initial':
            ck=ROOT/m['checkpoints'][state]['path'];assert hashlib.sha256(ck.read_bytes()).hexdigest()==m['checkpoints'][state]['sha256'];model.load_state_dict(torch.load(ck,weights_only=True,map_location='cpu'))
        params=list(model.features.parameters())
        for batch,(x,y,v,h) in enumerate(batches):
            losses=terms(model(x),y,v);grad={}
            for k,value in losses.items():grad[k]=torch.cat([g.flatten() for g in torch.autograd.grad(value,params,retain_graph=True)])
            grad['base']=grad['heatmap']+grad['coordinate']+grad['visibility']
            norms={k:float(g.norm()) for k,g in grad.items()};cos={}
            for a,b in itertools.combinations(grad,2):
                denom=norms[a]*norms[b];cos[a+'_vs_'+b]=float(torch.dot(grad[a],grad[b])/denom) if denom else None
            rows.append(dict(state=state,batch_start=m['batch_starts'][batch],pixels_sha256=h,losses={k:float(v.detach()) for k,v in losses.items()},gradient_norms=norms,cosines=cos,geometry_base_norm_ratio=norms['geometry']/norms['base']))
    summary={state:dict(ratio_mean=float(np.mean([r['geometry_base_norm_ratio'] for r in rows if r['state']==state])),geometry_base_cosines=[r['cosines']['geometry_vs_base'] for r in rows if r['state']==state],geometry_visibility_cosines=[r['cosines']['visibility_vs_geometry'] for r in rows if r['state']==state]) for state in ('initial','control','geometry')}
    report=dict(plan_sha256=hashlib.sha256(p.read_bytes()).hexdigest(),rows=rows,summary=summary,hardware_writes=0,physical_movements=0,qualification_installed=False,limitations=['CPU frozen snapshots on128 reused training images; not optimizer trajectories or causal proof','Raw gradients omit AdamW state and do not justify a new coefficient alone','No retraining or runtime changes'])
    out=AI/'eval/gradient_diagnostic_v0_report.json'
    if out.exists():raise FileExistsError(out)
    out.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(summary,indent=2))
if __name__=='__main__':run()
