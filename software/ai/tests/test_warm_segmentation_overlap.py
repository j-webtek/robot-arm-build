import copy
import hashlib
import json
import sys
from pathlib import Path
import pytest
AI=Path(__file__).resolve().parents[1];ROOT=AI.parents[1];sys.path.insert(0,str(AI))
from vision.audit_warm_segmentation_overlap import analyze, index


def fixture():
    def rows(values):
        return [dict(seed=i,condition='standard',maximum_mm=v) for i,v in enumerate(values)]
    report=dict(results={a:dict(rows=rows(v)) for a,v in dict(baseline=[4,2,4],control=[4,3,4],occlusion=[3,3.01,4]).items()})
    prior=[dict(r,trained_failure_count=6 if i==2 else 0) for i,r in enumerate(rows([0,0,0]))]
    return report,prior


def test_known_transitions_and_strict_threshold():
    report,prior=fixture();rows,s=analyze([report,copy.deepcopy(report)],prior);a=s['all']
    assert a['recovered_by_seed']==[1,1] and a['introduced_by_seed']==[1,1]
    assert a['consistently_recovered']==a['consistently_introduced']==1
    assert a['persistent_all_pairs']==a['prior_still_bad_all_candidates']==1
    assert rows[0]['pairs'][0]['delta_maximum_mm']==-1


@pytest.mark.parametrize('mutation',['duplicate','missing','nonfinite','baseline'])
def test_reject_mismatched_evidence(mutation):
    report,prior=fixture();other=copy.deepcopy(report)
    target=other['results']['occlusion']['rows']
    if mutation=='duplicate':target.append(target[0])
    if mutation=='missing':target.pop()
    if mutation=='nonfinite':target[0]['maximum_mm']=float('nan')
    if mutation=='baseline':other['results']['baseline']['rows'][0]['maximum_mm']=4.1
    with pytest.raises(ValueError):analyze([report,other],prior)


def test_frozen_report_and_population_recount():
    p=AI/'eval/warm_segmentation_overlap_v0_plan.json';plan=json.loads(p.read_text())
    for f,h in plan['file_sha256'].items():assert hashlib.sha256((ROOT/f).read_bytes()).hexdigest()==h
    reports=[json.loads((ROOT/f).read_text()) for f in plan['reports']]
    prior=json.loads((ROOT/plan['prior']).read_text())
    rows,summaries=analyze(reports,[dict(r,maximum_mm=0.) for r in prior['rows']])
    result=json.loads((AI/'eval/warm_segmentation_overlap_v0_report.json').read_text())
    assert result['plan_sha256']==hashlib.sha256(p.read_bytes()).hexdigest()
    assert result['rows']==rows and result['summaries']==summaries
    assert summaries['all']['cases']==800
    for i in range(3):
        a=summaries['all'];assert a['candidate_tails'][i]==a['control_tails'][i]-a['recovered_by_seed'][i]+a['introduced_by_seed'][i]
    assert result['hardware_writes']==result['physical_movements']==result['new_forward_passes']==result['optimizer_updates']==0
    assert not result['qualification_installed']
