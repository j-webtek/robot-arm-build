import hashlib,json,sys
from pathlib import Path
AI=Path(__file__).resolve().parents[1];ROOT=AI.parents[1];sys.path[:0]=[str(AI),str(AI.parent/'src')]
import numpy as np
from vision.landmark_occlusions import render_controlled
from vision.synthetic_keyboard import catalog_for_workspace

def run():
    p=AI/'eval/refined_bias_v0_plan.json';m=json.loads(p.read_text())
    for f,h in m['file_sha256'].items():assert hashlib.sha256((ROOT/f).read_bytes()).hexdigest()==h
    source=json.loads((AI/'eval/visible_candidate_v0_report.json').read_text());catalog=catalog_for_workspace(ROOT);rows=[]
    for old in source['rows']:
        _,label,_=render_controlled(old['seed'],catalog,old['condition'],'ellipse')
        truth=np.array([[v['x_px']*610/256,v['y_px']*457/192] for v in label['landmarks']]);points=np.array(old['candidate']['points'])
        errors=points-truth;common=errors.mean(0);centered=errors-common
        norms=np.linalg.norm(errors,axis=1);energy=(errors**2).sum()
        rows.append(dict(seed=old['seed'],condition=old['condition'],corner_error_mm=norms.tolist(),common_bias_mm=common.tolist(),common_norm_mm=float(np.linalg.norm(common)),
            common_energy_fraction=float(4*(common**2).sum()/energy) if energy else 0.,centered_rms_mm=float(np.sqrt(np.mean(np.sum(centered**2,axis=1)))),
            largest_corner_energy_fraction=float((norms**2).max()/energy) if energy else 0.,fit_rms_mm=float(np.sqrt(old['candidate']['residual_mm2'])),
            maximum_key_error_mm=old['arms']['subpixel']['maximum_mm']))
    summaries={}
    for c in m['conditions']:
        selected=[r for r in rows if r['condition']==c];bad=[r for r in selected if r['maximum_key_error_mm']>3]
        summaries[c]=dict(cases=len(selected),bad=len(bad),common_mean_mm=float(np.mean([r['common_norm_mm'] for r in selected])),
            bad_common_majority=sum(r['common_energy_fraction']>=.5 for r in bad),bad_single_corner_majority=sum(r['largest_corner_energy_fraction']>=.5 for r in bad),
            low_residual_bad=sum(r['fit_rms_mm']<=3 for r in bad),low_residual_total=sum(r['fit_rms_mm']<=3 for r in selected),
            residual_error_correlation=float(np.corrcoef([r['fit_rms_mm'] for r in selected],[r['maximum_key_error_mm'] for r in selected])[0,1]))
    report=dict(plan_sha256=hashlib.sha256(p.read_bytes()).hexdigest(),rows=rows,summaries=summaries,hardware_writes=0,physical_movements=0,qualification_installed=False,
        limitations=['Oracle truth only diagnoses errors; no runtime offset or calibration','Common and largest-corner majority categories can overlap','Fixed3mm residual and50% energy descriptive cuts, not admission thresholds','Reused development and synthetic projection; residual is not calibrated uncertainty'])
    out=AI/'eval/refined_bias_v0_report.json'
    if out.exists():raise FileExistsError(out)
    out.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(summaries,indent=2))
if __name__=='__main__':run()
