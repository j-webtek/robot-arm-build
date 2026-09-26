import hashlib,json,sys
from pathlib import Path
AI=Path(__file__).resolve().parents[1];sys.path.insert(0,str(AI))
from vision.diagnose_landmark_visibility_response import summarize

def test_targeted_and_global_response_are_distinguished():
    def row(condition,p,t):return dict(seed=0,condition=condition,visibility_probabilities=p,visibility_targets=t)
    a=row('standard',[.9]*4,[1]*4)
    result=summarize([a,row('full',[.1,.8,.8,.8],[0,1,1,1])])
    assert abs(result['selectivity_mean']-.7)<1e-12
    assert result['threshold_crossings']==1
    global_result=summarize([a,row('full',[.1]*4,[0,1,1,1])])
    assert abs(global_result['selectivity_mean'])<1e-12

def test_frozen_reports_and_recomputation():
    p=AI/'vision/landmark_visibility_response_plan.json';m=json.loads(p.read_text())
    assert hashlib.sha256((AI/'vision/diagnose_landmark_visibility_response.py').read_bytes()).hexdigest()==m['source_sha256']
    r=json.loads((AI/'eval/landmark_visibility_response.json').read_text())
    assert r['plan_sha256']==hashlib.sha256(p.read_bytes()).hexdigest()
    for name,item in m['inputs'].items():
        path=AI/item['path'];assert hashlib.sha256(path.read_bytes()).hexdigest()==item['sha256']
        assert summarize(json.loads(path.read_text())['cases'])==r['results'][name]
    assert r['hardware_writes']==r['physical_movements']==0
    assert not r['qualification_installed']
