import hashlib,json,math,sys
from pathlib import Path
AI=Path(__file__).resolve().parents[1];ROOT=AI.parents[1]
sys.path[:0]=[str(AI),str(AI.parent/'src')]
from vision.evaluate_disagreement_uncertainty import bin_index


def test_bin_boundaries():
    assert [bin_index(v,[.25,.5,1]) for v in [0,.25,.25001,.5,.50001,1,1.01]]==[0,0,1,1,2,2,3]


def test_radius_support_abstention_and_metrics():
    path=AI/'eval/disagreement_uncertainty_v0.manifest.json';m=json.loads(path.read_text())
    r=json.loads((AI/'eval/disagreement_uncertainty_v0_report.json').read_text())
    assert hashlib.sha256(path.read_bytes()).hexdigest()==r['manifest_sha256']
    for f,h in m['file_sha256'].items():assert hashlib.sha256((ROOT/f).read_bytes()).hexdigest()==h
    assert len(r['fitting_cases'])==4200 and len(r['evaluation_cases'])==1400
    for index,radius in enumerate(r['radii_mm']):
        groups={}
        for c in r['fitting_cases']:
            if c['bin']==index:groups[c['seed']]=max(groups.get(c['seed'],0),c['maximum_error_mm'])
        assert len(groups)==r['bin_support_groups'][index]
        assert radius==(sorted(groups.values())[math.ceil(.99*len(groups))-1] if len(groups)>=50 else None)
    for c in r['evaluation_cases']:
        assert c['bin']==bin_index(c['disagreement_mm'],m['bin_edges_mm'])
        radius=r['radii_mm'][c['bin']]
        assert c['accepted']==(radius is not None and radius<=3)
        assert c['covered']==(c['maximum_error_mm']<=radius if c['accepted'] else None)
        if not c['accepted']:assert c['all_targets_fit'] is None
    for condition,metrics in r['metrics'].items():
        accepted=[c for c in r['evaluation_cases'] if c['condition']==condition and c['accepted']]
        assert metrics['accepted']==len(accepted)
        assert metrics['coverage']==(sum(c['covered'] for c in accepted)/len(accepted) if accepted else None)
        assert metrics['containment']==(sum(c['all_targets_fit'] for c in accepted)/len(accepted) if accepted else None)
    assert r['hardware_writes']==r['physical_movements']==0 and not r['qualification_installed']


def test_group_criteria_do_not_count_abstentions_as_success():
    r=json.loads((AI/'eval/disagreement_uncertainty_v0_report.json').read_text())
    groups=[]
    for seed in range(15000000,15000200):
        cases=[c for c in r['evaluation_cases'] if c['seed']==seed and c['accepted']]
        if cases:groups.append(dict(seed=seed,covered=all(c['covered'] for c in cases),fit=all(c['all_targets_fit'] for c in cases)))
    assert groups==r['accepted_groups']
    coverage=sum(g['covered'] for g in groups)/len(groups) if groups else None
    fit=sum(g['fit'] for g in groups)/len(groups) if groups else None
    assert (coverage,fit)==(r['group_coverage'],r['group_containment'])
    passed=bool(groups) and coverage>=.95 and fit>=.95 and all(v['acceptance_fraction']>=.1 and v['coverage']>=.95 and v['containment']>=.95 for v in r['metrics'].values())
    assert passed==r['feasibility_passed']
