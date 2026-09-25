"""Public saved-campaign action reads only the assigned root; native data is fake."""

import json
from pathlib import Path

import pytest

from rocell.application.wizard_actions import WizardError
from rocell.application.wizard_diagnostic_export import verify_export
from rocell.application.endpoint_campaign_import import summarize_saved_endpoint_campaign
from test_arrival_wizard_service import make_service, _run, _ticket
from test_endpoint_campaign_import import exported


def test_public_saved_review_and_export_round_trip(make_service,tmp_path,monkeypatch):
    service,runner,_=make_service(mode='physical')
    root,attempt,plan,_,_=exported(tmp_path,monkeypatch)
    assert root==service.export_directory
    values={'plan_json':plan.canonical_bytes.decode(),'attempt_ids':attempt}
    preview=_ticket(service,'review_endpoint_campaign',values)
    assert str(root) in ' '.join(preview['effects'])
    completed=_run(service,'review_endpoint_campaign',values)
    assert completed['status']=='SUCCEEDED',completed
    report=completed['result']['steps'][0]['report']
    assert report['selected_attempt_ids']==[attempt]
    assert report['trials'][0]['eligible_for_descriptive_comparison']
    assert not runner.calls
    export=_run(service,'export_logs')
    assert export['status']=='SUCCEEDED'
    folder=Path(export['result']['receipt']['path'])
    assert verify_export(folder)['valid']
    saved=json.loads((folder/f"attachment-result-{completed['operation_id'].removeprefix('operation-')}.json").read_bytes())
    assert saved['steps'][0]['report']==report


@pytest.mark.parametrize('selection',['../report','operation-'+'a'*32+' operation-'+'a'*32,''])
def test_bad_selection_refused_before_execution(make_service,tmp_path,monkeypatch,selection):
    service,runner,_=make_service()
    _,_,plan,_,_=exported(tmp_path,monkeypatch,invalid=True)
    with pytest.raises(WizardError): _ticket(service,'review_endpoint_campaign',
        {'plan_json':plan.canonical_bytes.decode(),'attempt_ids':selection})
    assert not runner.calls


def test_cancellation_check_prevents_any_import(tmp_path,monkeypatch):
    from rocell.application import endpoint_campaign_import as module
    def refused(): raise ValueError('cancelled')
    monkeypatch.setattr(module,'load_endpoint_observation',lambda *a:pytest.fail('No reads after cancellation'))
    with pytest.raises(ValueError,match='cancelled'):
        summarize_saved_endpoint_campaign(tmp_path,None,['operation-'+'a'*32],check_current=refused)
