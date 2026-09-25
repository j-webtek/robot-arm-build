"""New-profile transport against a loopback server only; never the robot."""
import pytest
from pathlib import Path
from rocell.application import supported_recovery_start as module
from rocell.application.first_motion_contract import canonical
from test_supported_recovery_start import inputs
from test_servo_diagnostic_start_http import once_server
from test_servo_diagnostic_http import response


def six_inputs():
    policy,challenge,_=inputs()
    policy.update(schema='rocell.six_count_recovery_policy.v1',initial_residual_counts=6)
    plan=module.freeze_recovery_plan(policy,boot_id=challenge['boot_id'],
        command_id='r18-six-count-recovery',profile='six_count')
    return policy,challenge,plan


@pytest.mark.parametrize('accepted',[True,False])
def test_six_count_sender_one_loopback_request(accepted):
    policy,challenge,plan=six_inputs()
    reply=response(canonical(dict(accepted=accepted,retry_allowed=False)),
        status=b'202 Accepted' if accepted else b'400 Bad Request')
    with once_server(reply) as (port,requests):
        sender=module.RecoveryStartSender('127.0.0.1',port,policy,profile='six_count')
        result=sender.send(plan,challenge,b'k'*32)
        with pytest.raises(ValueError):sender.send(plan,challenge,b'k'*32)
    assert len(requests)==1
    assert requests[0][2]==module.sign_recovery(plan,challenge,b'k'*32,
        approved_policy=policy,profile='six_count')
    assert result['endpoint_verified'] is result['retry_allowed'] is False


@pytest.mark.parametrize('failure',['send','pre-export','post-export'])
def test_six_count_durable_claim_and_export_failure(tmp_path,monkeypatch,failure):
    policy,challenge,plan=six_inputs();calls=[]
    original=module.WizardDiagnosticExporter.export
    def export(self,*args,**kwargs):
        if failure=='pre-export' or failure=='post-export' and calls:raise OSError('fixture')
        return original(self,*args,**kwargs)
    monkeypatch.setattr(module.WizardDiagnosticExporter,'export',export)
    class Sender:
        def send(self,*args):
            assert len(list(tmp_path.glob('diagnostic-start-*.json')))==1
            calls.append(1)
            raise OSError('fixture')
    if failure=='send':
        result=module.send_prepared_recovery(tmp_path,Sender(),plan,challenge,b'k'*32,
            approved_policy=policy,profile='six_count')
        assert result['delivery']['result']=='DELIVERY_UNCERTAIN'
    else:
        with pytest.raises(OSError):module.send_prepared_recovery(tmp_path,Sender(),plan,
            challenge,b'k'*32,approved_policy=policy,profile='six_count')
    assert len(calls)==(failure!='pre-export')
    if calls:
        monkeypatch.setattr(module.WizardDiagnosticExporter,'export',original)
        with pytest.raises(Exception):module.send_prepared_recovery(tmp_path,Sender(),plan,
            challenge,b'k'*32,approved_policy=policy,profile='six_count')
        assert len(calls)==1


def test_staged_board_profile_is_explicit_and_startup_unchanged():
    tools=Path(__file__).resolve().parents[2]/'.firmware-tools'
    old=tools/'configured-diagnostic-candidate-r17/RoArm-M3_example'
    new=tools/'configured-diagnostic-candidate-r18/RoArm-M3_example'
    assert (new/'diagnostic_boot.h').read_bytes()==(old/'diagnostic_boot.h').read_bytes()
    owner=(new/'configured_native_owner.h').read_text()
    assert owner.startswith('#define ROCELL_SIX_COUNT_RECOVERY 1\n')
    assert 'Esp32StartCrypto,true,6>' in owner
    assert '"r18-six-count-recovery"' in (new/'configured_recovery_board_routes.h').read_text()
    for name in ('configured_pair_board_routes.h','controller_pair_config.h','elbow_gain_routes.h'):
        assert (old/name).read_bytes()==(new/name).read_bytes()
