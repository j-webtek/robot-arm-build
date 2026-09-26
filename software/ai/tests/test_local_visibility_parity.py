import hashlib,json,sys
from pathlib import Path
import numpy as np
AI=Path(__file__).resolve().parents[1];ROOT=AI.parents[1];sys.path.insert(0,str(AI))
from vision.diagnose_local_visibility_parity import compare

def test_frozen_parity_and_peak_changes():
    p=AI/'eval/local_visibility_parity_plan.json';m=json.loads(p.read_text());r=json.loads((AI/'eval/local_visibility_parity_report.json').read_text())
    assert r['plan_sha256']==hashlib.sha256(p.read_bytes()).hexdigest()
    for f,h in m['file_sha256'].items():assert hashlib.sha256((ROOT/f).read_bytes()).hexdigest()==h
    runs={k:{a:np.array(b) for a,b in v.items()} for k,v in r['runs'].items()}
    for mode in ('cpu_32','cuda_1','cuda_32'):
        c=compare(runs['cpu_1'],runs[mode]);assert c==r['comparisons']['cpu_1_vs_'+mode]
        for i,j in c['changed_indices']:assert runs['cpu_1']['peaks'][i,j]!=runs[mode]['peaks'][i,j]
    retained=json.loads((AI/'eval/landmark_local_visibility_v0_local_scorecard.json').read_text())
    assert r['pixels_sha256']==retained['development_pixels_sha256']
    assert np.array_equal(runs['cuda_32']['probabilities'],np.array([c['visibility_probabilities'] for c in retained['cases']]))
    assert r['hardware_writes']==r['physical_movements']==0
    assert not r['qualification_installed']
