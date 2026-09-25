import json
from pathlib import Path

import pytest

from rocell.application.hold_command_contract import HoldPlan, freeze_hold_plan, sign_hold
from rocell.application.hold_prepared_start import HoldStartSender, send_prepared_hold


def fixture():
    policy = dict(acceleration=1, age_us=250000, baseline_gap_us=100000,
        deadline_us=2000000, drift=2, joints=[[p-8,p+8] for p in (2048,2390,1727,2723,2041,2042,2051)],
        maximum_gap_us=500000, pair_us=10000, permit_explicit_enable=0, scan_us=100000,
        schema='rocell.hold_policy.v1', servo_id=14, settle_us=100000, speed=20)
    plan = freeze_hold_plan(policy, boot_id='11'*16, command_id='reviewed-hold')
    challenge = dict(schema='rocell.start_challenge.v1', boot_id='11'*16,
                     nonce='22'*32, issued_us=1000, expires_us=10001000)
    return policy, plan, challenge


class Sender:
    def __init__(self, root, fail=False):
        self.root, self.fail, self.calls = root, fail, 0

    def send(self, plan, challenge, key):
        self.calls += 1
        assert len(list(self.root.glob('diagnostic-start-*.json'))) == 1
        previews = list(self.root.glob('wizard-*/attachment-hold-plan.json'))
        assert previews
        if self.fail:
            raise RuntimeError('PRIVATE-EXCEPTION-DO-NOT-EXPORT')
        return dict(result='CONTROLLER_REPORTED_ACCEPTANCE', write_verified=False)


@pytest.mark.parametrize('fail', [False, True])
def test_prepare_claim_send_export_once(tmp_path, fail):
    policy, plan, challenge = fixture()
    root = tmp_path / 'exports'
    sender = Sender(root, fail)
    report = send_prepared_hold(root, sender, plan, challenge, b'k'*32, approved_policy=policy)
    assert sender.calls == 1 and report['export_verified']
    assert report['delivery']['result'] == ('DELIVERY_UNCERTAIN' if fail else 'CONTROLLER_REPORTED_ACCEPTANCE')
    with pytest.raises(Exception):
        send_prepared_hold(root, sender, plan, challenge, b'k'*32, approved_policy=policy)
    assert sender.calls == 1
    for path in root.rglob('*.json'):
        assert 'PRIVATE-EXCEPTION' not in path.read_text()
        assert 'kkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkk' not in path.read_text()
    retained = json.loads((Path(report['export_path']) / 'attachment-prepared-hold.json').read_text())
    assert retained['retry_allowed'] is False


def test_frozen_policy_and_invalid_signing():
    policy, plan, challenge = fixture()
    policy['speed'] = 21
    with pytest.raises(ValueError):
        sign_hold(plan, challenge, b'k'*32, approved_policy=policy)
    policy, plan, challenge = fixture()
    for invalid in (HoldPlan(plan.encoded + b' ', plan.policy_encoded),
                    HoldPlan(plan.encoded, b'{}')):
        with pytest.raises(ValueError):
            sign_hold(invalid, challenge, b'k'*32, approved_policy=policy)
    with pytest.raises(ValueError):
        sign_hold(plan, dict(challenge, boot_id='33'*16), b'k'*32, approved_policy=policy)


def test_invalid_key_never_exports_or_calls_sender(tmp_path):
    policy, plan, challenge = fixture()
    root = tmp_path / 'exports'
    sender = Sender(root)
    with pytest.raises(ValueError):
        send_prepared_hold(root, sender, plan, challenge, bytes(32), approved_policy=policy)
    assert sender.calls == 0 and not root.exists()


def test_real_sender_connection_failure_is_one_use(tmp_path, monkeypatch):
    policy, plan, challenge = fixture()
    attempts = []
    def unavailable(*args, **kwargs):
        attempts.append(True)
        raise OSError('mock network unavailable')
    monkeypatch.setattr('rocell.application.servo_diagnostic_start_http.socket.socket', unavailable)
    sender = HoldStartSender('192.168.0.225', 8081, policy)
    assert attempts == []
    report = send_prepared_hold(tmp_path / 'exports', sender, plan, challenge,
                                b'k'*32, approved_policy=policy)
    assert len(attempts) == 1 and sender.attempted
    assert report['delivery']['endpoint_verified'] is False
    with pytest.raises(ValueError):
        sender.send(plan, challenge, b'k'*32)
    assert len(attempts) == 1
