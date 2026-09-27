import hashlib,json,sys
from pathlib import Path
from unittest.mock import patch
AI=Path(__file__).resolve().parents[1];ROOT=AI.parents[1];sys.path[:0]=[str(AI),str(AI.parent/'src')]
from rocell_ai.local_baseline_demo import semantic,html_document


def test_repeated_keys_and_unsupported_intents():
    observation=dict(ref='fixture',fresh=True,phone_state='not_visible')
    _,result=semantic('Type "hello" on the keyboard',observation)
    assert [a['key'] for a in result['action_plan']['actions']]==['H','E','L','L','O']
    for request in ['Type it on the keyboard','Call 5550100 on the phone']:
        assert semantic(request,observation)[1]['status']=='blocked'
    assert semantic('Type "hello" on the keyboard',dict(observation,fresh=False))[1]['reason']=='stale_observation'


def test_html_embedded_json_cannot_end_script():
    payload={'request':'</script><script>alert(1)</script>&'}
    document=html_document(payload)
    embedded=document.split('<script id="report" type="application/json">')[1].split('</script>')[0]
    assert '<' not in embedded and json.loads(embedded)==payload
    assert '__REPORT_JSON__' not in document


def test_demo_lineage_and_decisions():
    p=AI/'eval/local_baseline_demo_v0_plan.json';plan=json.loads(p.read_text())
    r=json.loads((AI/'eval/local_baseline_demo_v0/report.json').read_text())
    assert r['plan_sha256']==hashlib.sha256(p.read_bytes()).hexdigest()
    from evidence_artifacts import verify_frozen_artifacts
    verify_frozen_artifacts(ROOT,plan['file_sha256'])
    assert [c['motion_status'] for c in r['cases']]==['PERCEPTION_EVIDENCE_REQUIRED','PERCEPTION_EVIDENCE_REQUIRED','PERCEPTION_ABSTAIN_OBSTRUCTED','STALE_OBSERVATION','CLARIFICATION_REQUIRED','UNSUPPORTED_REQUEST']
    assert all(c['motion_batch'] is None and c['hardware_writes']==c['physical_movements']==0 for c in r['cases'])
    import base64,math
    for c in r['cases']:
        assert hashlib.sha256(base64.b64decode(c['image_data_uri'].split(',')[1])).hexdigest()==c['image_sha256']
        for t in c['targets']:assert t['error_mm']==math.dist(t['predicted_xy_mm'],t['simulation_truth_xy_mm'])
    assert r['hardware_writes']==r['physical_movements']==0 and not r['qualification_installed']


def test_truth_does_not_enter_motion_decision():
    from rocell_ai.shared_shadow_runner_v2 import run_shared_shadow_v2
    observation=dict(ref='fixture',fresh=True,obstructed=False)
    with patch('rocell_ai.shared_shadow_runner_v2.assemble',side_effect=AssertionError('must not assemble')):
        result=run_shared_shadow_v2(request_id='test',request='Type "hello" on the keyboard',observation=observation,context=None,inputs=None)
    assert result['status']=='PERCEPTION_EVIDENCE_REQUIRED'
    assert not result['physical_authority'] and result['hardware_commands_generated']==0
