import json
from pathlib import Path
import pytest
from rocell.application.cartesian_export_review import review_cartesian_export, validate_export_id
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter
from rocell.application.wizard_worker import run
from test_wifi_cartesian import setup
from test_movement_campaign_ui import render
from test_arrival_wizard_service import make_service, _run, _ticket


def retained_trial(tmp_path):
    moves=tmp_path/'moves';moves.mkdir()
    _,execute,*_=setup(moves,mode='unchanged',elbow_only=True)
    result=execute()
    source=dict(schema='rocell.native_cartesian_trial.v1',status=result['status'],run=result)
    (tmp_path/'software/runs').mkdir(parents=True,exist_ok=True)
    exporter=WizardDiagnosticExporter((tmp_path/'software/runs/wizard-exports').resolve())
    exporter.prepare(create=True)
    receipt=exporter.export(dict(mode='test'),[],attachments={
        'cartesian-trial.json':json.dumps(source).encode()})
    return Path(receipt['path'])


def test_worker_and_ui_review_real_saved_transaction_without_replay(tmp_path):
    folder=retained_trial(tmp_path)
    result=run(tmp_path,'review_cartesian_export',dict(export_id=folder.name),'test')
    report=result['steps'][0]['report']
    assert report['source_status']=='COMPLETION_DEADLINE_EXCEEDED'
    assert report['next_step']=='INVESTIGATE_JOINT_RESPONSE_BEFORE_MORE_MOTION'
    rows={r['joint']:r for r in report['joint_comparison']}
    assert rows['e']['response']=='NO_REPORTED_RESPONSE'
    assert rows['t']['response']=='UNCOMMANDED_OBSERVATION'
    assert rows['t']['predicted_goal_count'] is None
    assert result['motion_command_count']==0 and result['device_open_count']==0
    page=render(dict(action_id='review_cartesian_export',result=result))
    assert 'Saved joint-response review' in page and 'NO_REPORTED_RESPONSE' in page
    assert 'NOT QUALIFIED' in page and 'not commanded' in page


def test_tampered_source_rejected(tmp_path):
    folder=retained_trial(tmp_path)
    path=folder/'attachment-cartesian-trial.json'
    path.write_text('{}')
    with pytest.raises(ValueError,match='verification failed'):
        review_cartesian_export(tmp_path,folder.name)


@pytest.mark.parametrize('value',['../elsewhere','C:\\elsewhere','wizard-foo','',True])
def test_only_export_id_not_arbitrary_path_allowed(value):
    with pytest.raises(ValueError):validate_export_id(value)


def test_report_requires_no_hardware_authority_to_render(tmp_path):
    folder=retained_trial(tmp_path)
    result=run(tmp_path,'review_cartesian_export',dict(export_id=folder.name),'test')
    result['steps'][0]['report']['motion_authorized']=True
    page=render(dict(action_id='review_cartesian_export',result=result))
    assert 'unavailable or inconsistent' in page
    assert 'NO_REPORTED_RESPONSE' not in page


@pytest.mark.parametrize('mode',['physical','rehearsal'])
def test_review_action_runs_through_service_and_exports(make_service,tmp_path,mode):
    folder=retained_trial(tmp_path)
    service,runner,_=make_service(mode=mode)
    runner.run=lambda action,values,**kw:run(tmp_path,action,values,kw['cell_id'])
    supplied=dict(export_id=folder.name)
    _ticket(service,'review_cartesian_export',supplied)
    operation=_run(service,'review_cartesian_export',supplied)
    assert operation['status']=='SUCCEEDED',operation
    report=operation['result']['steps'][0]['report']
    assert report['joint_comparison'][2]['response']=='NO_REPORTED_RESPONSE'
    exported=_run(service,'export_logs')
    assert exported['status']=='SUCCEEDED'
    result_path=Path(exported['result']['receipt']['path'])/f"attachment-result-{operation['operation_id'].removeprefix('operation-')}.json"
    retained=json.loads(result_path.read_bytes())
    assert retained['steps'][0]['report']==report
