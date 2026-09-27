"""Descriptive failure audit; truth-derived categories never authorize runtime."""
import hashlib,json,sys
from pathlib import Path
import numpy as np
AI=Path(__file__).resolve().parents[1]


def classify(row):
    b=row['arms']['baseline']['maximum_mm']>3;c=row['arms']['candidate']['maximum_mm']>3
    return 'persistent' if b and c else 'introduced' if c else 'recovered' if b else 'both_within'


def summarize(rows):
    groups={k:[r for r in rows if classify(r)==k] for k in ['persistent','introduced','recovered','both_within']}
    result={}
    for name,group in groups.items():
        values=[r['arms']['candidate'] for r in group]
        result[name]=dict(images=len(group),scene_count=len({r['seed'] for r in group}),members=[dict(seed=r['seed'],condition=r['condition']) for r in group],
            candidate_max_error_p95=float(np.percentile([v['maximum_mm'] for v in values],95)) if values else None,
            candidate_max_error_max=max((v['maximum_mm'] for v in values),default=None),
            translation_over_3=sum(v['translation_mm']>3 for v in values),rotation_only_over_3=sum(v['rotation_only_maximum_mm']>3 for v in values),
            both_components_at_most_3_but_combined_over_3=sum(v['translation_mm']<=3 and v['rotation_only_maximum_mm']<=3 and v['maximum_mm']>3 for v in values))
    return result


def run():
    path=AI/'eval/grouped_failure_audit_v1_plan.json';p=json.loads(path.read_text());source=AI/p['source']
    assert hashlib.sha256(source.read_bytes()).hexdigest()==p['source_sha256']
    assert hashlib.sha256(Path(__file__).read_bytes()).hexdigest()==p['script_sha256']
    out=AI/'eval/grouped_failure_audit_v1_report.json'
    if out.exists():raise FileExistsError(out)
    evidence=json.loads(source.read_text());rows=evidence['rows']
    assert len(rows)==4000 and len({(r['seed'],r['condition']) for r in rows})==4000
    failure_seeds=sorted({r['seed'] for r in rows if r['arms']['candidate']['maximum_mm']>3})
    result=dict(plan_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),source_sha256=p['source_sha256'],overall=summarize(rows),conditions={c:summarize([r for r in rows if r['condition']==c]) for c in p['conditions']},candidate_failure_scenes=failure_seeds,
        available_runtime_quality_signals=[],new_fits=0,new_images=0,hardware_writes=0,physical_movements=0,qualification_installed=False,
        limitations=['Error decomposition and condition labels use simulation truth, not deployable observation-quality signals.','Translation and rotation-only errors are not additive or causal categories.','Consumed confirmation evidence; no threshold fitting, calibration or fresh confirmation.','Current report has no image-derived quality scores; cannot infer a usable abstention classifier from these summaries.'])
    out.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    print(json.dumps({k:{a:b for a,b in v.items() if a!='members'} for k,v in result['overall'].items()},indent=2));print('failure scenes',len(failure_seeds))
if __name__=='__main__':run()
