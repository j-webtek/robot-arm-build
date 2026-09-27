"""Review retained resolution evidence and exact feature shapes."""
import hashlib,json,sys
from pathlib import Path
AI=Path(__file__).resolve().parents[1];ROOT=AI.parents[1];sys.path.insert(0,str(AI))
import torch
from vision.pose_model import KeyboardPoseNet


def run():
    p=AI/'eval/representation_review_v0_plan.json';plan=json.loads(p.read_text())
    for f,h in plan['file_sha256'].items():assert hashlib.sha256((ROOT/f).read_bytes()).hexdigest()==h
    resolution=json.loads((AI/'eval/matched_resolution_v0_scorecard.json').read_text());a,b=resolution['results'];model=KeyboardPoseNet().eval();shapes={}
    for width,height in [(128,96),(256,192)]:
        x=torch.zeros(1,3,height,width);trace=[]
        with torch.no_grad():
            for layer in model.features:x=layer(x);trace.append(dict(layer=type(layer).__name__,shape=list(x.shape)))
        shapes[f'{width}x{height}']=trace
    clutter=json.loads((AI/'eval/clutter_ablation_v0_report.json').read_text())
    report=dict(plan_sha256=hashlib.sha256(p.read_bytes()).hexdigest(),resolution=[{k:r[k] for k in ['input_size','mean_mm','p95_mm','within_1mm_fraction','selected_epoch']} for r in [a,b]],
        larger_to_smaller_mean_ratio=b['mean_mm']/a['mean_mm'],parameter_count=sum(p.numel() for p in model.parameters()),feature_shapes=shapes,
        clutter_tails={m:sum(v['tail'] for v in cs.values()) for m,cs in clutter['summaries'].items()},
        decision='Retain128x96;do not repeat unchanged higher-resolution adaptation. Prepare a keyboard-versus-clutter segmentation auxiliary-head feasibility study; no adoption before paired evidence.',
        hardware_writes=0,physical_movements=0,qualification_installed=False,limitations=['Prior resolution run used one seed and starting weights trained at128x96','Feature shapes describe architecture,not proof of causal clutter failure','Auxiliary segmentation is an untested hypothesis; earlier landmark route failed and is not promoted','No fresh data,training,inference checkpoint selection or runtime change'])
    out=AI/'eval/representation_review_v0_report.json'
    if out.exists():raise FileExistsError(out)
    out.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:v for k,v in report.items() if k!='feature_shapes'},indent=2))
if __name__=='__main__':run()
