import hashlib,json,sys
from pathlib import Path
import numpy as np
AI=Path(__file__).resolve().parents[1];sys.path.insert(0,str(AI))
from vision.audit_grouped_failures import classify,summarize


def row(b,c):
    return dict(seed=1,condition='standard',arms={'baseline':{'maximum_mm':b},'candidate':dict(maximum_mm=c,translation_mm=2.,rotation_only_maximum_mm=2.)})


def test_categories_and_closed_threshold():
    assert [classify(row(b,c)) for b,c in [(4,4),(3,4),(4,3),(3,3)]]==['persistent','introduced','recovered','both_within']
    s=summarize([row(3,4)])
    assert s['introduced']['both_components_at_most_3_but_combined_over_3']==1
    assert s['persistent']['candidate_max_error_max'] is None


def test_report_full_partition_and_lineage():
    p=AI/'eval/grouped_failure_audit_v1_plan.json';plan=json.loads(p.read_text());source=AI/plan['source']
    assert hashlib.sha256(source.read_bytes()).hexdigest()==plan['source_sha256']
    assert hashlib.sha256((AI/'vision/audit_grouped_failures.py').read_bytes()).hexdigest()==plan['script_sha256']
    rows=json.loads(source.read_text())['rows'];r=json.loads((AI/'eval/grouped_failure_audit_v1_report.json').read_text())
    assert r['plan_sha256']==hashlib.sha256(p.read_bytes()).hexdigest()
    assert r['overall']==summarize(rows)
    members=[(v['seed'],v['condition']) for g in r['overall'].values() for v in g['members']]
    assert len(members)==len(set(members))==4000
    for condition in plan['conditions']:assert r['conditions'][condition]==summarize([v for v in rows if v['condition']==condition])
    failed=[v for v in rows if v['arms']['candidate']['maximum_mm']>3]
    assert len(failed)==121
    assert r['candidate_failure_scenes']==sorted({v['seed'] for v in failed})
    assert len(r['candidate_failure_scenes'])==57
    assert r['available_runtime_quality_signals']==[]
    assert r['new_fits']==r['new_images']==r['hardware_writes']==r['physical_movements']==0
    assert not r['qualification_installed']
