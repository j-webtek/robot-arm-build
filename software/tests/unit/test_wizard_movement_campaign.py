"""Public wizard preview/run/export using the real pure simulation worker."""

import json
from pathlib import Path
import pytest

from rocell.application.wizard_actions import ACTION_BY_ID, WizardError, validate_action_input
from rocell.application.wizard_movement_campaign import example_plan_text, parse_plan
from rocell.application.wizard_worker import run
from rocell.application.wizard_diagnostic_export import verify_export
from test_arrival_wizard_service import make_service, _run, _ticket, WORKSPACE


@pytest.mark.parametrize('mode',['physical','rehearsal'])
def test_public_preview_simulation_and_verified_export(make_service,mode):
    service,runner,_=make_service(mode=mode)
    runner.run=lambda action,values,**kw: run(WORKSPACE,action,values,kw['cell_id'])
    ticket=_ticket(service,'movement_campaign_preview')
    assert parse_plan(ticket['input']['plan_json']).sha256 in ' '.join(ticket['effects'])
    assert 'UNKNOWN' in ' '.join(ticket['effects'])
    operation=_run(service,'movement_campaign_simulate')
    assert operation['status']=='SUCCEEDED',operation
    report=operation['result']['steps'][0]['report']
    assert report['simulation']['status']=='MODEL_COMPLETED'
    assert report['campaign_analysis']['recommendation_status']=='NOT_QUALIFIED'
    assert len(report['campaign_analysis']['trials'])==2
    assert report['endpoint_campaign_analysis']['schema']=='rocell.endpoint_campaign_analysis.v1'
    assert report['endpoint_campaign_analysis']['observation_contract']=='SUPERVISED_ENDPOINT_ONLY'
    assert report['endpoint_campaign_analysis']['recommended_settings'] is None
    assert all(g['status']=='INSUFFICIENT_REPETITIONS' for g in report['endpoint_campaign_analysis']['groups'])
    assert not report['preview']['physical_ready']
    exported=_run(service,'export_logs')
    assert exported['status']=='SUCCEEDED'
    folder=Path(exported['result']['receipt']['path'])
    assert verify_export(folder)['valid']
    retained=json.loads((folder/f"attachment-result-{operation['operation_id'].removeprefix('operation-')}.json").read_bytes())
    assert retained['steps'][0]['report']==report
    assert service.view()['arm']['status']=='NOT_CONNECTED'


def test_bad_plan_rejected_before_ticket(make_service):
    service,_,_=make_service()
    for text in ('{}','{"schema":1,"schema":2}',example_plan_text().replace('R_ctrl','board')):
        with pytest.raises(WizardError): _ticket(service,'movement_campaign_preview',{'plan_json':text})


def test_fault_rehearsal_retains_failure_without_claiming_motion_success():
    result=run(WORKSPACE,'movement_campaign_simulate',{'fault':'MALFORMED'},'synthetic')
    assert result['status']=='SUCCEEDED'  # diagnostic completed, modeled motion did not
    report=result['steps'][0]['report']
    assert report['simulation']['status']=='STOPPED'
    assert report['simulation']['skipped_trial_ids']==['back']
    assert result['motion_command_count']==0


def test_extra_command_fields_and_oversized_campaign_are_rejected():
    with pytest.raises(WizardError):
        validate_action_input(ACTION_BY_ID['movement_campaign_simulate'],{'raw_command':'{}'})
    data=json.loads(example_plan_text()); data['limits']['max_duration_s']=100
    for trial in data['trials']: trial['timeout_s']=11
    with pytest.raises(ValueError): parse_plan(json.dumps(data))
