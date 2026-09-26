"""Frozen pixel/device/batch inference comparison; research only."""
import hashlib,json,sys
from pathlib import Path
AI=Path(__file__).resolve().parents[1];ROOT=AI.parents[1]
sys.path[:0]=[str(AI),str(AI.parent/'src')]
import numpy as np
import torch
from vision.temperature_visibility_model import TemperatureVisibilityNet
from vision.landmark_occlusions import render_controlled
from vision.synthetic_keyboard import catalog_for_workspace
from vision.evaluate_dark_only_normalization import normalize

def compare(a,b):
    return dict(peak_changes=int((a['peaks']!=b['peaks']).sum()),decision_changes=int(((a['probabilities']>=.5)!=(b['probabilities']>=.5)).sum()),max_probability_delta=float(np.max(np.abs(a['probabilities']-b['probabilities']))),changed_indices=np.argwhere((a['probabilities']>=.5)!=(b['probabilities']>=.5)).tolist())

def run(mode):
    p=AI/f'eval/temperature_visibility_{mode}_parity_plan.json';m=json.loads(p.read_text())
    for f,h in m['file_sha256'].items():assert hashlib.sha256((ROOT/f).read_bytes()).hexdigest()==h
    ck=ROOT/m['checkpoint'];assert hashlib.sha256(ck.read_bytes()).hexdigest()==m['checkpoint_sha256']
    assert torch.cuda.is_available(),'CUDA required for complete comparison'
    torch.set_num_threads(4);catalog=catalog_for_workspace(ROOT);pixels=[];labels=[]
    for seed in range(15000000,15000200):
        for condition in m['conditions']:
            image,label,_=render_controlled(seed,catalog,condition,'ellipse');image,_=normalize(image)
            pixels.append(np.asarray(image,dtype=np.uint8).transpose(2,0,1).copy());labels.append(label)
    x=np.stack(pixels);training=json.loads((AI/f'eval/landmark_temperature_v0_{mode}_scorecard.json').read_text())
    pixel_hash=hashlib.sha256(x.tobytes()).hexdigest();assert pixel_hash==training['development_pixels_sha256']
    runs={}
    for device in ('cpu','cuda'):
        model=TemperatureVisibilityNet(mode).to(device);model.load_state_dict(torch.load(ck,map_location=device,weights_only=True));model.eval()
        for batch in (1,32):
            peaks=[];probabilities=[];margins=[]
            with torch.no_grad():
                for start in range(0,len(x),batch):
                    out=model(torch.from_numpy(x[start:start+batch]).to(device).float()/255)
                    h=out['heatmap_logits'].flatten(2);top=h.topk(2,dim=-1).values
                    peaks.extend(h.argmax(-1).cpu().tolist());probabilities.extend(out['visibility_logits'].sigmoid().cpu().tolist());margins.extend((top[:,:,0]-top[:,:,1]).cpu().tolist())
            runs[f'{device}_{batch}']=dict(peaks=np.array(peaks),probabilities=np.array(probabilities),margins=np.array(margins))
    comparisons={f'cpu_1_vs_{k}':compare(runs['cpu_1'],v) for k,v in runs.items() if k!='cpu_1'}
    comparisons['cuda_32_vs_retained']=dict(decision_changes=int(((runs['cuda_32']['probabilities']>=.5)!=(np.array([c['visibility_probabilities'] for c in training['cases']])>=.5)).sum()),max_probability_delta=float(np.max(np.abs(runs['cuda_32']['probabilities']-np.array([c['visibility_probabilities'] for c in training['cases']])))))
    report=dict(plan_sha256=hashlib.sha256(p.read_bytes()).hexdigest(),pixels_sha256=pixel_hash,torch_version=torch.__version__,cuda_version=torch.version.cuda,device=torch.cuda.get_device_name(0),comparisons=comparisons,runs={k:{a:b.tolist() for a,b in v.items()} for k,v in runs.items()},hardware_writes=0,physical_movements=0,qualification_installed=False,limitations=['Same reused synthetic pixels/checkpoint; no retraining or qualification','Observed device/batch effects do not establish cross-platform bounds','Hard argmax discontinuities can magnify small numeric differences; no correction applied'])
    out=AI/f'eval/temperature_visibility_{mode}_parity_report.json'
    if out.exists():raise FileExistsError(out)
    out.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(comparisons,indent=2))
if __name__=='__main__':
    for mode in ('t1','t05'):run(mode)
