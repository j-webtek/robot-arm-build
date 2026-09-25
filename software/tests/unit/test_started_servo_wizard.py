from copy import deepcopy
from pathlib import Path

from test_arrival_wizard_service import make_service,_run
from test_movement_campaign_ui import render
from test_servo_prepared_start import Sender
from test_servo_diagnostic_start_http import native_plan,KEY
from rocell.application.first_motion_contract import canonical
from rocell.application.servo_prepared_start import send_prepared_start
from rocell.application.servo_started_run import collect_started_run


def saved_uncertain_run(root):
    plan,challenge=native_plan()
    prepared=send_prepared_start(root,Sender(root,True),plan,challenge,KEY)
    def reader(path,**kwargs):
        return canonical(dict(schema='rocell.diagnostic_transport.v3',instance_id=challenge['boot_id'],
            state='FAULT',reason='INTERFERING_COMMAND',records=0,storage_fault=False,
            start_supported=True,durable_export_verified=False))
    result=collect_started_run(root,Path(prepared['export_path']).name,reader)
    return result,prepared


def test_wizard_reviews_delivery_separately_from_endpoint(make_service):
    service,runner,_=make_service(mode='physical')
    saved,_=saved_uncertain_run(service.export_directory)
    operation=_run(service,'review_started_servo_run',{'export_id':Path(saved['export_path']).name})
    assert operation['status']=='SUCCEEDED',operation
    report=operation['result']['steps'][0]['report']
    assert report['schema']=='rocell.started_run_review.v1' and report['replay_verified']
    assert report['delivery']['result']=='DELIVERY_UNCERTAIN'
    assert report['outcome']['status']=='EVIDENCE_REJECTED'
    page=render(operation)
    for label in ['Command delivery and telemetry','DELIVERY_UNCERTAIN','NOT QUALIFIED',
                  'Evidence rejected','challenge claim remains consumed','does not verify arrival']:
        assert label in page
    assert not runner.calls and service.view()['arm']['status']=='NOT_CONNECTED'
    forged=deepcopy(operation)
    forged['result']['steps'][0]['report']['delivery']['endpoint_verified']=True
    assert 'unavailable or inconsistent' in render(forged)


def test_modified_claim_cannot_be_reviewed_as_success(make_service):
    service,runner,_=make_service(mode='physical')
    saved,prepared=saved_uncertain_run(service.export_directory)
    (service.export_directory/prepared['claim_file']).write_bytes(b'{}')
    operation=_run(service,'review_started_servo_run',{'export_id':Path(saved['export_path']).name})
    assert operation['status']!='SUCCEEDED'
    assert not runner.calls
