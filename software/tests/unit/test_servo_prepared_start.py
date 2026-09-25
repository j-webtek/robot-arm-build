import json
import hashlib
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from rocell.application import servo_prepared_start as module
from rocell.application.servo_diagnostic_start_http import DiagnosticStartError,DiagnosticStartSender
from test_servo_diagnostic_start_http import native_plan,KEY,once_server
from test_servo_diagnostic_http import response
from rocell.application.first_motion_contract import canonical


class Sender:
    def __init__(self,root,uncertain=False):self.root=root;self.calls=0;self.uncertain=uncertain
    def send(self,plan,challenge,key):
        self.calls+=1
        claims=list(self.root.glob('diagnostic-start-*.json'));assert len(claims)==1
        claim=json.loads(claims[0].read_text())
        assert claim['state']=='CONSUMED_BEFORE_SEND' and claim['session_plan_sha256']==plan.sha256
        assert module.verify_export(self.root/claim['plan_export_id'])['valid']
        report=dict(schema='rocell.host_start_delivery.v1',result='DELIVERY_UNCERTAIN' if self.uncertain else 'CONTROLLER_REPORTED_ACCEPTANCE',
            session_plan_sha256=plan.sha256,command_id=plan.to_dict()['command']['command_id'],
            boot_id=challenge['boot_id'],connection_attempted=True,
            transmission_attempted=True,retry_allowed=False,progression_authority=False,endpoint_verified=False)
        if self.uncertain:raise DiagnosticStartError(report)
        return report


@pytest.mark.parametrize('uncertain',[False,True])
def test_claim_precedes_send_and_survives_new_sender(tmp_path,uncertain):
    plan,challenge=native_plan();sender=Sender(tmp_path,uncertain)
    result=module.send_prepared_start(tmp_path,sender,plan,challenge,KEY)
    assert sender.calls==1 and result['export_verified'] and not result['progression_authority']
    assert module.verify_export(Path(result['export_path']))['valid']
    another=Sender(tmp_path)
    with pytest.raises(Exception):module.send_prepared_start(tmp_path,another,plan,challenge,KEY)
    assert another.calls==0
    assert KEY.hex() not in Path(result['export_path'],'attachment-prepared-start.json').read_text()


@pytest.mark.parametrize('failure',['pre_export','verification','claim','post_export'])
def test_storage_faults_do_not_retry_or_erase_claim(tmp_path,monkeypatch,failure):
    plan,challenge=native_plan();sender=Sender(tmp_path)
    original=module.WizardDiagnosticExporter.export;calls=0
    def export(self,*args,**kwargs):
        nonlocal calls
        calls+=1
        if failure=='pre_export' or (failure=='post_export' and calls==2):raise OSError('injected storage failure')
        return original(self,*args,**kwargs)
    monkeypatch.setattr(module.WizardDiagnosticExporter,'export',export)
    if failure=='verification':monkeypatch.setattr(module,'verify_export',lambda _:dict(valid=False))
    if failure=='claim':
        def fail(*args,**kwargs):raise OSError('injected reservation failure')
        monkeypatch.setattr(module,'publish_reservation_bytes',fail)
    with pytest.raises((OSError,ValueError)):module.send_prepared_start(tmp_path,sender,plan,challenge,KEY)
    assert sender.calls==(1 if failure=='post_export' else 0)
    if failure=='post_export':assert len(list(tmp_path.glob('diagnostic-start-*.json')))==1


def test_incomplete_claim_is_consumed_not_repaired(tmp_path):
    plan,challenge=native_plan()
    digest=hashlib.sha256(canonical(dict(boot_id=challenge['boot_id'],nonce=challenge['nonce']))).hexdigest()
    claim=tmp_path/f'diagnostic-start-{digest}.json';claim.write_bytes(b'{')
    sender=Sender(tmp_path)
    with pytest.raises(Exception):module.send_prepared_start(tmp_path,sender,plan,challenge,KEY)
    assert sender.calls==0 and claim.read_bytes()==b'{'


def test_concurrent_attempts_share_one_claim(tmp_path):
    plan,challenge=native_plan();senders=[Sender(tmp_path),Sender(tmp_path)]
    def attempt(sender):
        try:return module.send_prepared_start(tmp_path,sender,plan,challenge,KEY)
        except Exception:return None
    with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(attempt,senders))
    assert sum(sender.calls for sender in senders)==1
    assert sum(result is not None for result in results)==1


def test_real_sender_loopback_and_verified_delivery_export(tmp_path):
    plan,challenge=native_plan()
    reply=response(canonical(dict(accepted=True,retry_allowed=False)),status=b'202 Accepted')
    with once_server(reply) as (port,requests):
        result=module.send_prepared_start(tmp_path,DiagnosticStartSender('127.0.0.1',port),plan,challenge,KEY)
    assert len(requests)==1 and result['export_verified']
    assert result['delivery']['result']=='CONTROLLER_REPORTED_ACCEPTANCE'
    assert not result['delivery']['endpoint_verified']
