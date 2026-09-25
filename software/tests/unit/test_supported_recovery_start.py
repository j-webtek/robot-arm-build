"""One-use preparation tests. Injected sender only; no device connections."""
import json
from pathlib import Path

import pytest
from rocell.application import supported_recovery_start as module
from rocell.application.first_motion_contract import canonical
from rocell.application.hold_command_contract import HoldPlan
from test_servo_diagnostic_start_http import once_server
from test_servo_diagnostic_http import response


def inputs():
    hold = dict(acceleration=1, age_us=250000, baseline_gap_us=100000,
        deadline_us=2000000, drift=2,
        joints=[[p-8, p+8] for p in (2048,2390,1727,2723,2041,2042,2051)],
        maximum_gap_us=500000, pair_us=10000, permit_explicit_enable=0,
        scan_us=100000, schema='rocell.hold_policy.v1', servo_id=14,
        settle_us=100000, speed=20)
    policy = dict(schema='rocell.supported_recovery_policy.v1', hold_policy=hold,
                  initial_residual_counts=5)
    challenge = dict(schema='rocell.start_challenge.v1', boot_id='11'*16,
        nonce='22'*32, issued_us=1000, expires_us=10001000)
    plan = module.freeze_recovery_plan(policy, boot_id=challenge['boot_id'], command_id='reviewed-recovery')
    return policy, challenge, plan


@pytest.mark.parametrize('failure', ['none', 'send', 'pre-export', 'claim', 'post-export'])
def test_prepared_recovery_consumes_before_send(tmp_path, monkeypatch, failure):
    policy, challenge, plan = inputs()
    calls = []
    original = module.WizardDiagnosticExporter.export
    def export(self, *args, **kwargs):
        if (failure == 'pre-export' or failure == 'post-export' and calls):
            raise OSError('Injected export failure')
        return original(self, *args, **kwargs)
    monkeypatch.setattr(module.WizardDiagnosticExporter, 'export', export)
    if failure == 'claim':
        def reject(*args, **kwargs): raise OSError('Injected reservation failure')
        monkeypatch.setattr(module, 'publish_reservation_bytes', reject)
    class Sender:
        def send(self, *args):
            # Durable reservation must already exist before this potentially physical effect.
            claims = list(tmp_path.glob('diagnostic-start-*.json'))
            assert len(claims) == 1
            assert json.loads(claims[0].read_bytes())['state'] == 'CONSUMED_BEFORE_SEND'
            calls.append(1)
            if failure == 'send': raise RuntimeError('private exception text must not leak')
            return dict(schema='rocell.host_recovery_delivery.v1',
                result='CONTROLLER_REPORTED_ACCEPTANCE', endpoint_verified=False,
                retry_allowed=False, progression_authority=False)
    if failure in ('pre-export', 'claim', 'post-export'):
        with pytest.raises(OSError):
            module.send_prepared_recovery(tmp_path, Sender(), plan, challenge, b'k'*32, approved_policy=policy)
    else:
        result = module.send_prepared_recovery(tmp_path, Sender(), plan, challenge, b'k'*32, approved_policy=policy)
        assert result['export_verified'] is True
        assert result['retry_allowed'] is result['progression_authority'] is False
        expected = 'DELIVERY_UNCERTAIN' if failure == 'send' else 'CONTROLLER_REPORTED_ACCEPTANCE'
        assert result['delivery']['result'] == expected
        assert 'private exception' not in canonical(result).decode()
    assert len(calls) == int(failure not in ('pre-export', 'claim'))
    if calls:
        monkeypatch.setattr(module.WizardDiagnosticExporter, 'export', original)
        with pytest.raises(Exception):
            module.send_prepared_recovery(tmp_path, Sender(), plan, challenge, b'k'*32, approved_policy=policy)
        assert len(calls) == 1


@pytest.mark.parametrize('mutation', ['ordinary', 'boot', 'bytes', 'residual', 'enable'])
def test_invalid_recovery_plan_cannot_prepare(tmp_path, mutation):
    policy, challenge, plan = inputs()
    if mutation == 'ordinary': plan = HoldPlan(plan.encoded, plan.policy_encoded)
    if mutation == 'boot': challenge['boot_id'] = '33'*16
    if mutation == 'bytes': plan = module.RecoveryPlan(plan.encoded+b' ', plan.policy_encoded)
    if mutation == 'residual': policy['initial_residual_counts'] = 6
    if mutation == 'enable': policy['hold_policy']['permit_explicit_enable'] = 1
    class Forbidden:
        def send(self, *args): pytest.fail('Unexpected send')
    with pytest.raises(ValueError):
        module.send_prepared_recovery(tmp_path, Forbidden(), plan, challenge, b'k'*32, approved_policy=policy)
    assert not list(tmp_path.iterdir())


def test_recovery_sender_prepares_exact_signed_token_without_connection(monkeypatch):
    policy, challenge, plan = inputs()
    sender = module.RecoveryStartSender('192.168.0.225', 8081, policy)
    policy['initial_residual_counts'] = 6  # sender owns its validated copy
    original_policy, _, _ = inputs()
    token, identity = sender._prepare_request(plan, challenge, b'k'*32)
    assert token == module.sign_recovery(plan, challenge, b'k'*32, approved_policy=original_policy)
    assert identity['command_id'] == 'reviewed-recovery'
    assert sender.attempted is False


@pytest.mark.parametrize('mode', ['accepted', 'rejected', 'lost', 'contradictory'])
def test_recovery_loopback_exact_token_and_one_attempt(mode):
    policy, challenge, plan = inputs()
    reply = response(canonical(dict(accepted=mode != 'rejected', retry_allowed=False)),
                     status=b'400 Bad Request' if mode == 'rejected' else b'202 Accepted')
    if mode == 'lost': reply = b''
    if mode == 'contradictory':
        reply = response(canonical(dict(accepted=True, retry_allowed=True)), status=b'202 Accepted')
    with once_server(reply) as (port, requests):
        sender = module.RecoveryStartSender('127.0.0.1', port, policy)
        if mode in ('lost', 'contradictory'):
            with pytest.raises(module.DiagnosticStartError) as error:
                sender.send(plan, challenge, b'k'*32)
            report = error.value.report
            assert report['result'] == 'DELIVERY_UNCERTAIN'
        else:
            report = sender.send(plan, challenge, b'k'*32)
            assert report['result'] == ('CONTROLLER_REPORTED_ACCEPTANCE' if mode == 'accepted'
                                        else 'CONTROLLER_REPORTED_REJECTION')
        with pytest.raises(ValueError): sender.send(plan, challenge, b'k'*32)
    assert len(requests) == 1
    assert requests[0][0][0] == b'POST /rocell/diagnostics/start HTTP/1.1'
    assert requests[0][2] == module.sign_recovery(plan, challenge, b'k'*32, approved_policy=policy)
    assert report['schema'] == 'rocell.host_recovery_delivery.v1'
    assert report['endpoint_verified'] is report['retry_allowed'] is report['progression_authority'] is False
