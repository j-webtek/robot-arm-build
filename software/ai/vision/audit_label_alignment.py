import hashlib,json,math,sys
from pathlib import Path
from unittest.mock import patch
AI=Path(__file__).resolve().parents[1];ROOT=AI.parents[1];sys.path[:0]=[str(AI),str(AI.parent/'src')]
import numpy as np
from PIL import ImageDraw
from vision.landmark_occlusions import render_controlled
from vision.synthetic_keyboard import catalog_for_workspace

def run():
    p=AI/'eval/label_alignment_v0_plan.json';m=json.loads(p.read_text())
    for f,h in m['file_sha256'].items():assert hashlib.sha256((ROOT/f).read_bytes()).hexdigest()==h
    source=json.loads((AI/'eval/visible_candidate_v0_report.json').read_text());catalog=catalog_for_workspace(ROOT);rows=[];max_draw=0.;max_formula=0.
    original=ImageDraw.ImageDraw.polygon
    for old in source['rows']:
        calls=[]
        def capture(self,xy,*args,**kwargs):
            calls.append(np.array(xy));return original(self,xy,*args,**kwargs)
        with patch.object(ImageDraw.ImageDraw,'polygon',capture):_,label,_=render_controlled(old['seed'],catalog,old['condition'],'ellipse')
        cx,cy,angle=label['pose'];c,s=math.cos(angle),math.sin(angle);rotation=np.array([[c,-s],[s,c]])
        local=np.array([[-157.5,-73.5],[157.5,-73.5],[157.5,73.5],[-157.5,73.5]])
        expected=(local@rotation.T+[cx,cy])*[256/610,192/457]
        labels=np.array([[v['x_px'],v['y_px']] for v in label['landmarks']])
        max_draw=max(max_draw,float(np.max(np.abs(calls[0]-labels))));max_formula=max(max_formula,float(np.max(np.abs(expected-labels))))
        errors=(np.array(old['candidate']['points'])-labels*[610/256,457/192])@rotation
        for i,error in enumerate(errors):rows.append(dict(seed=old['seed'],condition=old['condition'],corner=i,local_error_mm=error.tolist(),geometric_visibility=label['landmarks'][i]['unoccluded_fraction']))
    summaries={}
    for condition in m['conditions']:
        summaries[condition]={}
        for i in range(4):
            selected=[r for r in rows if r['condition']==condition and r['corner']==i];e=np.array([r['local_error_mm'] for r in selected])
            summaries[condition][str(i)]=dict(mean_local_xy_mm=e.mean(0).tolist(),median_local_xy_mm=np.median(e,axis=0).tolist(),mean_norm_mm=float(np.linalg.norm(e,axis=1).mean()))
    report=dict(plan_sha256=hashlib.sha256(p.read_bytes()).hexdigest(),images=len(source['rows']),max_draw_label_delta_px=max_draw,max_independent_formula_delta_px=max_formula,rows=rows,summaries=summaries,hardware_writes=0,physical_movements=0,qualification_installed=False,limitations=['Verifies vector polygon arguments,not raster edge visibility after blur/clutter','Signed errors from selected refined heatmap candidates,not raw heatmap logits','Synthetic geometry and reused development only; no empirical correction or physical calibration'])
    out=AI/'eval/label_alignment_v0_report.json'
    if out.exists():raise FileExistsError(out)
    out.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(dict(max_draw=max_draw,max_formula=max_formula,summaries=summaries),indent=2))
if __name__=='__main__':run()
