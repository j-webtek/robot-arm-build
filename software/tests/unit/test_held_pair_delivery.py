"""Loopback delivery failures; source-chain replay is covered by native integration."""
import hashlib
from pathlib import Path
import pytest
from rocell.application import held_pair_delivery as module
from rocell.application.held_pair_prepared_authorization import PreparedPairAuthorization
from rocell.application.physical_onboarding_durability import PhysicalOnboardingDurabilityError
from rocell.application.first_motion_contract import canonical
from test_servo_diagnostic_start_http import once_server
from test_servo_diagnostic_http import response


@pytest.mark.parametrize('reply,expected',[
    (b'','DELIVERY_UNCERTAIN'),
    (response(canonical(dict(accepted=False,retry_allowed=False)),status=b'400 Bad Request'),
     'CONTROLLER_REPORTED_REJECTION'),
    (response(canonical(dict(accepted=False,retry_allowed=False)),status=b'202 Accepted'),
     'DELIVERY_UNCERTAIN'),
])
def test_one_shot_uncertain_delivery(tmp_path,monkeypatch,reply,expected):
    identity=dict(boot_id='11'*16,session_sha256='22'*32,leg='forward',
                  context_export_id='test-context',context_sha256='33'*32)
    unsigned=b'synthetic-envelope'
    monkeypatch.setattr(module,'_source',lambda *args:(unsigned,identity,'diagnostic-delivery-test.json'))
    authorization=PreparedPairAuthorization(unsigned+b'x'*32,'test-context','unused','22'*32)
    with once_server(reply) as (port,requests):
        result=module.send_authorized_pair(tmp_path,authorization,leg='forward',address='127.0.0.1',port=port)
    assert len(requests)==1
    assert result['report']['delivery']['result']==expected
    assert not result['endpoint_verified'] and not result['progression_authority']
    assert module.replay_pair_delivery(tmp_path,Path(result['export_path']).name)['replay_verified']
    with pytest.raises(PhysicalOnboardingDurabilityError):
        module.send_authorized_pair(tmp_path,authorization,leg='forward',address='127.0.0.1',port=port)
    assert authorization.token not in canonical(result)


def test_failed_report_export_consumes_attempt(tmp_path,monkeypatch):
    identity=dict(boot_id='11'*16,session_sha256='22'*32,leg='return',
                  context_export_id='test-context',context_sha256='33'*32)
    unsigned=b'synthetic-envelope'
    monkeypatch.setattr(module,'_source',lambda *args:(unsigned,identity,'diagnostic-delivery-test.json'))
    authorization=PreparedPairAuthorization(unsigned+b'x'*32,'test-context','unused','22'*32)
    export=module.WizardDiagnosticExporter.export
    def fail_result(self,*args,**kwargs):
        if 'pair-delivery-result.json' in kwargs.get('attachments',{}):raise OSError('Disk failure')
        return export(self,*args,**kwargs)
    monkeypatch.setattr(module.WizardDiagnosticExporter,'export',fail_result)
    with once_server(b'') as (port,requests):
        with pytest.raises(OSError):
            module.send_authorized_pair(tmp_path,authorization,leg='return',address='127.0.0.1',port=port)
    assert len(requests)==1
    with pytest.raises(PhysicalOnboardingDurabilityError):
        module.send_authorized_pair(tmp_path,authorization,leg='return',address='127.0.0.1',port=port)
