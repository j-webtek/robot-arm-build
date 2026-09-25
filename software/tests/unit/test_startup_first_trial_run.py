"""One-shot orchestration tests, using exports and synthetic network replies."""
import hashlib
import json
from pathlib import Path

import pytest
from rocell.application.first_motion_contract import canonical
from rocell.application.startup_first_trial_run import run_first_trial
from rocell.application.servo_transport_snapshot import STATUS
from rocell.application.servo_diagnostic_start_http import DiagnosticStartError

BOOT = '22' * 16


@pytest.mark.parametrize('delivery', ['accepted', 'uncertain'])
def test_one_send_then_evidence_only(tmp_path, delivery):
    config = json.loads((Path(__file__).resolve().parents[2] / 'docs/startup-r6-policy-draft.json').read_bytes())
    calls = []
    phase = {'sent': False}
    def get(path, **limits):
        assert path == STATUS
        calls.append('get')
        return canonical(dict(schema='rocell.diagnostic_transport.v3', instance_id=BOOT,
            state='FAULT' if phase['sent'] else 'IDLE',
            reason='STARTUP_READ_FAILED' if phase['sent'] else 'NOT_CONFIGURED', records=0,
            storage_fault=False, start_supported=True, durable_export_verified=False))
    def discover(boot):
        calls.append('challenge')
        assert boot == BOOT
        return dict(challenge=dict(schema='rocell.start_challenge.v1', boot_id=BOOT,
            nonce='33'*32, issued_us=1000, expires_us=10001000))
    class Sender:
        def send(self, plan, challenge, key):
            calls.append('send')
            phase['sent'] = True
            report = dict(schema='rocell.host_startup_delivery.v1', connection_attempted=True,
                transmission_attempted=True, retry_allowed=False, progression_authority=False,
                endpoint_verified=False, result='DELIVERY_UNCERTAIN',
                startup_plan_sha256=hashlib.sha256(plan.encoded).hexdigest(),
                boot_id=BOOT, command_id='first-test')
            if delivery == 'uncertain': raise DiagnosticStartError(report)
            body = canonical(dict(accepted=True, retry_allowed=False))
            return dict(report, result='CONTROLLER_REPORTED_ACCEPTANCE', response_body=body.decode(),
                        response_sha256=hashlib.sha256(body).hexdigest())
    def pause(seconds):
        assert seconds == 4.0
        calls.append('pause')
    args = dict(configuration=config, expected_boot=BOOT, command_id='first-test', key=b'K'*32,
                get_bytes=get, discover=discover, sender=Sender(), pause=pause)
    result = run_first_trial(tmp_path, **args)
    assert result['outcome'] == dict(status='INCONCLUSIVE', assessment=None)
    assert result['export_verified'] and result['replay_verified']
    assert calls.count('send') == calls.count('challenge') == 1
    assert calls.index('send') < calls.index('pause') < len(calls)-1
    # Even if a stale endpoint incorrectly reports IDLE again, durable boot claim
    # prevents a second challenge/send from a new runner invocation.
    phase['sent'] = False
    with pytest.raises(Exception): run_first_trial(tmp_path, **args)
    assert calls.count('send') == calls.count('challenge') == 1


def test_invalid_key_prevents_even_status_access(tmp_path):
    config = json.loads((Path(__file__).resolve().parents[2] / 'docs/startup-r6-policy-draft.json').read_bytes())
    def forbidden(*args, **kwargs): raise AssertionError('Unexpected device access')
    with pytest.raises(ValueError):
        run_first_trial(tmp_path, configuration=config, expected_boot=BOOT, command_id='bad',
            key=b'', get_bytes=forbidden, discover=forbidden, sender=None, pause=forbidden)
