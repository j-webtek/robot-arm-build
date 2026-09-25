"""Pure signing with synthetic key/boot; never grants installation authority."""
import copy
import hmac
import pytest
from test_observed_pose_candidate import inputs
from rocell.application.observed_pose_candidate import draft_settings
from rocell.application import observed_pose_recovery as module
from rocell.application.supported_recovery_start import freeze_recovery_plan


@pytest.fixture
def context(monkeypatch):
    hold, pair = draft_settings(*inputs())
    report = dict(hold_settings=hold, pair_settings=pair)
    monkeypatch.setattr(module, 'replay_candidate', lambda *args: dict(report=copy.deepcopy(report)))
    challenge = dict(schema='rocell.start_challenge.v1', boot_id='11'*16,
                     nonce='22'*32, issued_us=1000, expires_us=10001000)
    return report, challenge


def test_signs_exact_profile(context):
    _, challenge = context
    plan = module.freeze_observed_recovery('unused', 'candidate', boot_id=challenge['boot_id'])
    token = module.sign_observed_recovery('unused', 'candidate', plan, challenge, b'k'*32)
    assert token.endswith(hmac.digest(b'k'*32, token[:-32], 'sha256'))
    assert module.COMMAND.encode() in token


@pytest.mark.parametrize('fault', ['command', 'boot', 'policy'])
def test_rejects_mixed_frozen_plan(context, fault):
    _, challenge = context
    policy = module.recovery_policy_from_candidate('unused', 'candidate')
    if fault == 'policy': policy['hold_policy']['joints'][1][0] -= 1
    plan = freeze_recovery_plan(policy, boot_id='33'*16 if fault=='boot' else challenge['boot_id'],
        command_id='r18-six-count-recovery' if fault=='command' else module.COMMAND,
        profile='six_count')
    with pytest.raises(ValueError, match='mismatch'):
        module.sign_observed_recovery('unused', 'candidate', plan, challenge, b'k'*32)


@pytest.mark.parametrize('field', ['hold_settings', 'pair_settings'])
def test_rejects_changed_public_candidate(context, field):
    report, _ = context
    if field == 'hold_settings': report[field]['hold_policy']['speed'] = 21
    else: report[field]['offset_counts'] = 6
    with pytest.raises(ValueError, match='Exact observed'):
        module.recovery_policy_from_candidate('unused', 'candidate')
