import hashlib,json,sys
from pathlib import Path
AI=Path(__file__).resolve().parents[1];ROOT=AI.parents[1]
sys.path[:0]=[str(AI),str(AI.parent/'src')]
from vision.diagnose_normalization_crossings import transition


def test_exact_threshold_transitions():
    assert transition(3,3)=='stable_pass'
    assert transition(3,3.001)=='new_failure'
    assert transition(3.001,3)=='recovered'
    assert transition(4,5)=='persistent_failure'


def test_retained_case_accounting_and_provenance():
    path=AI/'eval/normalization_crossings_v0.manifest.json';m=json.loads(path.read_text())
    r=json.loads((AI/'eval/normalization_crossings_v0_report.json').read_text())
    source=json.loads((ROOT/m['scorecard']).read_text())
    assert hashlib.sha256(path.read_bytes()).hexdigest()==r['manifest_sha256']
    for f,h in m['file_sha256'].items():assert hashlib.sha256((ROOT/f).read_bytes()).hexdigest()==h
    for condition,groups in r['transitions'].items():
        cases=[c for c in source['cases'] if c['condition']==condition]
        assert sum(g['count'] for g in groups.values())==200
        for name,g in groups.items():
            seeds=[c['seed'] for c in cases if transition(c['arms']['control']['maximum_mm'],c['arms']['normalized']['maximum_mm'])==name]
            assert seeds==g['seeds'] and len(seeds)==g['count']
        summaries=source['summaries'][condition]
        assert groups['persistent_failure']['count']+groups['new_failure']['count']==summaries['normalized']['above_3mm_images']
        assert groups['persistent_failure']['count']+groups['recovered']['count']==summaries['control']['above_3mm_images']
    expected=[c for c in source['cases'] if c['condition']=='appearance_shift' and max(c['arms'][a]['maximum_mm'] for a in c['arms'])>3]
    assert [c['seed'] for c in expected]==[c['seed'] for c in r['appearance_details']]
    for before,after in zip(expected,r['appearance_details']):
        assert before['arms']==after['arms'] and before['gain']==after['gain']
    assert r['hardware_writes']==r['physical_movements']==0
    assert not r['qualification_installed']
