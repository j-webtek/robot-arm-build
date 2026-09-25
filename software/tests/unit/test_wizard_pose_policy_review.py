from pathlib import Path
import pytest
from rocell.application.wizard_worker import run
from rocell.application.wizard_actions import ACTION_BY_ID
from test_arrival_wizard_service import make_service, _run, _ticket, WORKSPACE
from rocell.application.wizard_diagnostic_export import verify_export
import json


def test_registered_worker_passes_receipts_without_hardware(tmp_path,monkeypatch):
    from rocell.application import pose_policy_review
    calls=[]
    def review(root,**values):
        calls.append((root,values))
        return dict(schema='rocell.pose_policy_comparison.v1',hardware_access=False,
            motion_authorized=False,incompatible_servo_ids=[12,13,15,17])
    monkeypatch.setattr(pose_policy_review,'build_review',review)
    values=dict(pose_export='pose',stage_export='stage',installation_export='installation')
    result=run(tmp_path,'review_pose_policy',values,'test-review')
    assert calls==[(tmp_path/'software',values)]
    assert result['steps'][0]['report']['motion_authorized'] is False
    assert ACTION_BY_ID['review_pose_policy'].worker=='pose_policy_review'


def test_worker_propagates_failed_receipt_replay(tmp_path,monkeypatch):
    from rocell.application import pose_policy_review
    def reject(*a,**k):raise ValueError('Receipt mismatch')
    monkeypatch.setattr(pose_policy_review,'build_review',reject)
    with pytest.raises(ValueError,match='Receipt mismatch'):
        run(tmp_path,'review_pose_policy',dict(pose_export='pose',stage_export='stage',
            installation_export='installation'),'test-review')


@pytest.mark.parametrize('mode',['physical','rehearsal'])
def test_public_preview_run_and_export(make_service,monkeypatch,mode):
    from rocell.application import pose_policy_review
    report=dict(schema='rocell.pose_policy_comparison.v1',hardware_access=False,
        motion_authorized=False,incompatible_servo_ids=[12,13,15,17],
        base_to_board_registration='UNKNOWN_AFTER_REPOSITION')
    monkeypatch.setattr(pose_policy_review,'build_review',lambda *a,**k:dict(report))
    service,runner,_=make_service(mode=mode)
    runner.run=lambda action,values,**kw:run(WORKSPACE,action,values,kw['cell_id'])
    values=dict(pose_export='pose',stage_export='stage',installation_export='installation')
    ticket=_ticket(service,'review_pose_policy',values)
    assert 'no hardware access' in ' '.join(ticket['effects'])
    operation=_run(service,'review_pose_policy',values)
    assert operation['status']=='SUCCEEDED'
    assert operation['result']['steps'][0]['report']==report
    exported=_run(service,'export_logs')
    folder=Path(exported['result']['receipt']['path'])
    assert verify_export(folder)['valid']
    retained=json.loads((folder/f"attachment-result-{operation['operation_id'].removeprefix('operation-')}.json").read_bytes())
    assert retained['steps'][0]['report']==report
    assert service.view()['arm']['status']=='NOT_CONNECTED'
