"""Training-only descriptive ranking audit, not threshold selection."""
import hashlib,json,math
from pathlib import Path
import numpy as np
AI=Path(__file__).resolve().parents[1]


def ranks(values):
    x=np.asarray(values);order=np.argsort(x,kind='stable');result=np.empty(len(x),float);i=0
    while i<len(x):
        j=i+1
        while j<len(x) and x[order[j]]==x[order[i]]:j+=1
        result[order[i:j]]=(i+j-1)/2;i=j
    return result


def auc(scores,errors):
    scores=np.asarray(scores);bad=np.asarray(errors)>3
    pos=scores[bad];neg=scores[~bad]
    if not len(pos) or not len(neg):return None
    return float(((pos[:,None]>neg[None,:])+.5*(pos[:,None]==neg[None,:])).mean())


def metrics(scores,errors,fractions):
    scores=np.asarray(scores);errors=np.asarray(errors)
    if len(scores)==0 or scores.shape!=errors.shape or not np.isfinite(scores).all() or not np.isfinite(errors).all():raise ValueError('invalid audit rows')
    a=ranks(scores);b=ranks(errors);corr=float(np.corrcoef(a,b)[0,1]) if np.std(a)>0 and np.std(b)>0 else None
    curve=[]
    for fraction in fractions:
        if not 0<fraction<=1:raise ValueError('invalid retention fraction')
        k=math.ceil(len(scores)*fraction);threshold=np.sort(scores)[k-1];chosen=errors[scores<=threshold]
        curve.append(dict(requested_fraction=fraction,selected=len(chosen),actual_fraction=len(chosen)/len(errors),diagnostic_scale_threshold=float(threshold),tail_count=int((chosen>3).sum()),tail_rate=float((chosen>3).mean()),mean_error_mm=float(chosen.mean()),max_error_mm=float(chosen.max())))
    return dict(rows=len(scores),tail_count=int((errors>3).sum()),tail_rate=float((errors>3).mean()),tail_auc=auc(scores,errors),spearman=corr,scale_min=float(scores.min()),scale_max=float(scores.max()),retention_curve=curve)


def run():
    path=AI/'eval/scale_ranking_v1_plan.json';plan=json.loads(path.read_text());source=AI/plan['source']
    assert hashlib.sha256(source.read_bytes()).hexdigest()==plan['source_sha256']
    assert hashlib.sha256(Path(__file__).read_bytes()).hexdigest()==plan['script_sha256']
    out=AI/'eval/scale_ranking_v1_report.json'
    if out.exists():raise FileExistsError(out)
    rows=json.loads(source.read_text())['rows'];assert len(rows)==4800
    def summarize(group):return {name:metrics([r[key] for r in group],[r['error_mm'] for r in group],plan['retention_fractions']) for name,key in [('image_scale','scale_mm'),('fold_constant','constant_scale_mm')]}
    scenes=[dict(seed=s,error_mm=max(r['error_mm'] for r in rows if r['seed']==s),scale_mm=max(r['scale_mm'] for r in rows if r['seed']==s),constant_scale_mm=max(r['constant_scale_mm'] for r in rows if r['seed']==s)) for s in sorted({r['seed'] for r in rows})]
    result=dict(plan_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),source_sha256=plan['source_sha256'],images=summarize(rows),scenes=summarize(scenes),conditions={c:summarize([r for r in rows if r['condition']==c]) for c in plan['conditions']},styles={s:summarize([r for r in rows if r['style']==s]) for s in ['rectangle','ellipse']},new_fits=0,new_images=0,hardware_writes=0,physical_movements=0,qualification_installed=False,limitations=['Out-of-fold uncertainty-training evidence only; no statistical-significance or independent confirmation claim.','Diagnostic thresholds are not selected, exported or admitted at runtime.','Ties are included in full, so actual retention may exceed requested fraction.','Scene maxima cover all eight variants; image rows are correlated.','Fold-constant ordering reflects fitted fold intercepts, not an image-dependent signal.'])
    out.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n');print(json.dumps(dict(images=result['images']['image_scale'],scenes=result['scenes']['image_scale'],condition_auc={c:v['image_scale']['tail_auc'] for c,v in result['conditions'].items()}),indent=2))
if __name__=='__main__':run()
