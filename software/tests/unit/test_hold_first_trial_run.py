"""Real exports and one-shot orchestration; all device I/O replaced locally."""
import hashlib
import json
from pathlib import Path

import pytest
from rocell.application.first_motion_contract import canonical
from rocell.application.hold_first_trial_run import run_first_hold
from rocell.application.hold_transport_snapshot import HoldHTTPReader
from rocell.application.hold_prepared_start import HoldStartSender
from rocell.application.servo_diagnostic_challenge import DiagnosticChallengeReader
from rocell.application.servo_transport_snapshot import STATUS

BOOT = '22' * 16


def config():
    return json.loads((Path(__file__).resolve().parents[2] /
                       'docs/hold-r7-policy-draft.json').read_bytes())


@pytest.mark.parametrize('outcome', ['accepted', 'uncertain', 'challenge_failure'])
def test_single_attempt_and_retained_fault(tmp_path, monkeypatch, outcome):
    calls = []
    sent = False
    def get(self, path, **kwargs):
        assert path == STATUS
        calls.append('get')
        return canonical(dict(schema='rocell.hold_transport.v1', instance_id=BOOT,
            state='FAULT' if sent else 'IDLE', reason='READ_FAILED' if sent else 'NOT_CONFIGURED',
            records=0, record_bytes=4096, storage_fault=False, durable_export_verified=False))
    def discover(self, boot):
        calls.append('challenge')
        assert boot == BOOT
        if outcome == 'challenge_failure':
            raise OSError('test-only challenge failure')
        return dict(challenge=dict(schema='rocell.start_challenge.v1', boot_id=BOOT,
            nonce='33'*32, issued_us=1000, expires_us=10001000))
    def send(self, plan, challenge, key):
        nonlocal sent
        sent = True
        calls.append('send')
        if outcome == 'uncertain':
            raise OSError('test-only lost response')
        doc = json.loads(plan.encoded)
        body = canonical(dict(accepted=True, retry_allowed=False))
        return dict(schema='rocell.host_hold_delivery.v1', connection_attempted=True,
            transmission_attempted=True, retry_allowed=False, progression_authority=False,
            endpoint_verified=False, result='CONTROLLER_REPORTED_ACCEPTANCE',
            hold_plan_sha256=hashlib.sha256(plan.encoded).hexdigest(),
            policy_sha256=doc['policy_sha256'], boot_id=BOOT, command_id=doc['command_id'],
            response_body=body.decode(), response_sha256=hashlib.sha256(body).hexdigest())
    def pause(seconds):
        assert seconds == 3.0
        calls.append('pause')
    monkeypatch.setattr(HoldHTTPReader, '_get', get)
    monkeypatch.setattr(DiagnosticChallengeReader, 'discover', discover)
    monkeypatch.setattr(HoldStartSender, 'send', send)
    args = dict(configuration=config(), expected_boot=BOOT, key=b'K'*32,
                address='192.168.0.225', authorized_powered_hold=True, pause=pause)
    if outcome == 'challenge_failure':
        with pytest.raises(OSError):
            run_first_hold(tmp_path, **args)
        assert 'send' not in calls
    else:
        result = run_first_hold(tmp_path, **args)
        assert result['assessment']['category'] == 'INCONCLUSIVE'
        assert result['replay_verified'] and result['retry_allowed'] is False
        assert calls.count('send') == 1
        assert calls.index('send') < calls.index('pause') < len(calls)-1
    assert calls.count('challenge') == 1
    before = list(calls)
    with pytest.raises(ValueError, match='consumed'):
        run_first_hold(tmp_path, **args)
    assert calls == before  # No second status/challenge/send.


@pytest.mark.parametrize('change', [dict(authorized_powered_hold=False), dict(key=b''),
                                  dict(expected_boot='invalid'), dict(address='example.com')])
def test_invalid_admission_has_no_io(tmp_path, monkeypatch, change):
    def forbidden(*args, **kwargs):
        pytest.fail('Unexpected device access')
    monkeypatch.setattr(HoldHTTPReader, '_get', forbidden)
    args = dict(configuration=config(), expected_boot=BOOT, key=b'K'*32,
                address='192.168.0.225', authorized_powered_hold=True)
    args.update(change)
    with pytest.raises(ValueError):
        run_first_hold(tmp_path, **args)


def test_export_failure_prevents_challenge(tmp_path, monkeypatch):
    from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter
    original = WizardDiagnosticExporter.export
    def export(self, context, *args, **kwargs):
        if context.get('mode') == 'first-hold-trial-plan':
            raise OSError('test disk failure')
        return original(self, context, *args, **kwargs)
    def get(self, path, **kwargs):
        return canonical(dict(schema='rocell.hold_transport.v1', instance_id=BOOT,
            state='IDLE', reason='NOT_CONFIGURED', records=0, record_bytes=4096,
            storage_fault=False, durable_export_verified=False))
    monkeypatch.setattr(WizardDiagnosticExporter, 'export', export)
    monkeypatch.setattr(HoldHTTPReader, '_get', get)
    monkeypatch.setattr(DiagnosticChallengeReader, 'discover',
                        lambda *a: pytest.fail('Challenge after export failure'))
    with pytest.raises(OSError):
        run_first_hold(tmp_path, configuration=config(), expected_boot=BOOT, key=b'K'*32,
                       address='192.168.0.225', authorized_powered_hold=True)
    assert (tmp_path / ('first-hold-trial-' + BOOT + '.json')).exists()
