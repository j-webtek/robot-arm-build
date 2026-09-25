import json
from pathlib import Path
import pytest
from test_product_ghost_endpoints import route
from test_movement_campaign_ui import render
from test_arrival_wizard_service import make_service, _run
from rocell.application.product_ghost_endpoints import rehearse_product_endpoints
from rocell.application.product_ghost_export_review import review_product_case
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter
from rocell.application.wizard_worker import run


def archive(root,fault='NONE',mutate=None):
    report=rehearse_product_endpoints(root,route(),fault=fault)
    (root/'software/runs').mkdir(parents=True,exist_ok=True)
    exporter=WizardDiagnosticExporter((root/'software/runs/wizard-exports').resolve())
    exporter.prepare(create=True)
    def save(name,data):
        return Path(exporter.export({},[],attachments={name:json.dumps(data).encode()})['path'])
    refs=[]
    for mapping,row in zip(report['trial_mapping'],report.pop('trial_results')):
        if mutate: mutate(row)
        path=save('product-leg.json',dict(parent_plan_sha256=report['plan_sha256'],mapping=mapping,result=row))
        refs.append(dict(**mapping,export=path.name))
    report['trial_exports']=refs
    return save('product-case.json',report),refs


@pytest.mark.parametrize('fault',['NONE','MISSING_FEEDBACK'])
def test_worker_reviews_traces_and_ui(tmp_path,fault):
    folder,_=archive(tmp_path,fault)
    result=run(tmp_path,'review_product_ghost_case',dict(export_id=folder.name),'test')
    report=result['steps'][0]['report']
    assert report['status']=='SAVED_SIMULATION_BEHAVIOR_VERIFIED'
    assert result['motion_command_count']==result['device_open_count']==0
    page=render(dict(action_id='review_product_ghost_case',result=result))
    assert 'Full-size keyboard simulation review' in page and report['status'] in page
    report['motion_authorized']=True
    assert 'unavailable or inconsistent' in render(dict(action_id='review_product_ghost_case',result=result))


def test_tampered_linked_leg_rejected(tmp_path):
    folder,refs=archive(tmp_path)
    linked=folder.parent/refs[0]['export']/'attachment-product-leg.json'
    linked.write_text('{}')
    with pytest.raises(ValueError,match='verification failed'):
        review_product_case(tmp_path,folder.name)


def test_arbitrary_path_rejected(tmp_path):
    with pytest.raises(ValueError): review_product_case(tmp_path,'../elsewhere')


@pytest.mark.parametrize('kind',['wire','input_plan','request_binding','authority'])
def test_valid_archive_with_inconsistent_leg_rejected(tmp_path,kind):
    def mutate(row):
        if kind=='wire': row['simulated_wire_writes']=['{"T":104,"z":999}\n']
        if kind=='input_plan': row['input_plan_sha256']='0'*64
        if kind=='request_binding': row['trial']['request_sha256']='0'*64
        if kind=='authority': row['physical_authority']=True
    folder,_=archive(tmp_path,mutate=mutate)
    with pytest.raises(ValueError): review_product_case(tmp_path,folder.name)


@pytest.mark.parametrize('mode',['physical','rehearsal'])
def test_service_review_and_export(make_service,tmp_path,mode):
    folder,_=archive(tmp_path)
    service,runner,_=make_service(mode=mode)
    runner.run=lambda action,values,**kw:run(tmp_path,action,values,kw['cell_id'])
    operation=_run(service,'review_product_ghost_case',dict(export_id=folder.name))
    assert operation['status']=='SUCCEEDED'
    exported=_run(service,'export_logs')
    assert exported['status']=='SUCCEEDED'
