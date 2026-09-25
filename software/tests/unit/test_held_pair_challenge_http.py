"""Localhost only; never a robot challenge or discovery request."""
import pytest
from rocell.application.first_motion_contract import canonical
from rocell.application.held_pair_challenge_http import request_pair_challenge, ROUTES
from rocell.application.physical_onboarding_durability import PhysicalOnboardingDurabilityError
from test_servo_diagnostic_start_http import once_server
from test_servo_diagnostic_http import response
from rocell.application import held_pair_challenge_http as module
from rocell.application.held_pair_receipt_workflow import authorize_pair_from_receipt
from pathlib import Path


@pytest.mark.parametrize('operation',['prepare','return','recovery'])
@pytest.mark.parametrize('fault',[None,'lost','boot','redirect','malformed'])
def test_challenge_single_post(tmp_path,operation,fault):
    challenge=dict(schema='rocell.start_challenge.v1',boot_id=('33' if fault=='boot' else '11')*16,
                   nonce='22'*32,issued_us=1000,expires_us=10001000)
    reply=response(canonical(challenge))
    if fault=='lost':reply=b''
    if fault=='redirect':reply=response(canonical(challenge),status=b'302 Found')
    if fault=='malformed':reply=response(b'{}')
    with once_server(reply) as (port,requests):
        saved=request_pair_challenge(tmp_path,operation=operation,expected_boot='11'*16,address='127.0.0.1',port=port)
    result=saved['report']['result']
    assert result['category']==('CHALLENGE_RECEIVED' if fault is None else 'CHALLENGE_UNCERTAIN')
    assert result['transmission_attempted'] and not result['progression_authority']
    assert result['challenge']==(challenge if fault is None else None)
    assert len(requests)==1 and requests[0][2]==b''
    replay=module.replay_pair_challenge(tmp_path,Path(saved['export_path']).name)
    assert replay['replay_verified'] and replay['report']==saved['report']
    if fault is not None:
        with pytest.raises(ValueError,match='Confirmed challenge receipt'):
            authorize_pair_from_receipt(tmp_path,Path(saved['export_path']).name,'unused',b'k'*32,
                                        leg='forward' if operation=='prepare' else 'return')
    with pytest.raises(ValueError,match='Confirmed challenge receipt'):
        authorize_pair_from_receipt(tmp_path,Path(saved['export_path']).name,'unused',b'k'*32,
                                    leg='return' if operation=='prepare' else 'forward')
    assert requests[0][0][0]==f'POST {ROUTES[operation]} HTTP/1.1'.encode()
    with pytest.raises(PhysicalOnboardingDurabilityError):
        request_pair_challenge(tmp_path,operation=operation,expected_boot='11'*16,address='127.0.0.1',port=port)


def test_challenge_export_failure_never_retries(tmp_path,monkeypatch):
    original=module.WizardDiagnosticExporter.export
    def fail_report(self,*args,**kwargs):
        if 'pair-challenge-result.json' in kwargs.get('attachments',{}):raise OSError('Synthetic disk failure')
        return original(self,*args,**kwargs)
    monkeypatch.setattr(module.WizardDiagnosticExporter,'export',fail_report)
    with once_server(b'') as (port,requests):
        with pytest.raises(OSError):
            request_pair_challenge(tmp_path,operation='prepare',expected_boot='11'*16,address='127.0.0.1',port=port)
    assert len(requests)==1
    with pytest.raises(PhysicalOnboardingDurabilityError):
        request_pair_challenge(tmp_path,operation='prepare',expected_boot='11'*16,address='127.0.0.1',port=port)


def test_invalid_challenge_request_has_no_network(tmp_path,monkeypatch):
    monkeypatch.setattr(module.socket,'socket',lambda *a,**kw:pytest.fail('Unexpected network'))
    for kwargs in (dict(operation='reset',expected_boot='11'*16,address='127.0.0.1'),
                   dict(operation='prepare',expected_boot='bad',address='127.0.0.1'),
                   dict(operation='prepare',expected_boot='11'*16,address='example.com')):
        with pytest.raises(ValueError):request_pair_challenge(tmp_path,**kwargs)
