"""Local receipt/export boundaries; no device access in these tests."""
import json
from pathlib import Path
import pytest
from rocell.application import r16_hold_launch as module


@pytest.fixture
def prepared(tmp_path, monkeypatch):
    config = (Path(__file__).resolve().parents[2] /
              'docs/hold-r7-supported-pose-draft.json').read_bytes()
    (tmp_path / 'docs').mkdir()
    (tmp_path / 'docs/hold-r7-supported-pose-draft.json').write_bytes(config)
    exports = tmp_path / 'runs/wizard-exports'
    exports.mkdir(parents=True)
    binding = dict(expected_boot='12'*16, address='192.168.0.225',
                   startup_export_id='startup', motion_authorized=False)
    monkeypatch.setattr(module, 'review_recovery_startup', lambda root, ident: binding)
    return tmp_path, exports, binding


@pytest.mark.parametrize('claim', ['first-hold-trial-', 'supported-recovery-trial-'])
def test_consumed_boot_never_delegates(prepared, monkeypatch, claim):
    root, exports, binding = prepared
    (exports / (claim + binding['expected_boot'] + '.json')).write_text('{}')
    monkeypatch.setattr(module, 'run_first_hold', lambda *a, **k: pytest.fail('Device access'))
    with pytest.raises(ValueError, match='consumed'):
        module.run_r16_hold(root, startup_export_id='startup', key=b'k'*32,
                            authorized_powered_hold=True)


def test_ordinary_policy_and_boot_forwarded_with_retained_intent(prepared, monkeypatch):
    root, exports, binding = prepared
    calls = []
    def trial(path, **kwargs):
        calls.append(kwargs)
        assert path == exports
        assert list(exports.glob('wizard-*/attachment-hold-launch-binding.json'))
        return {'test_only': True}
    monkeypatch.setattr(module, 'run_first_hold', trial)
    result = module.run_r16_hold(root, startup_export_id='startup', key=b'k'*32,
                                 authorized_powered_hold=True)
    assert len(calls) == 1
    assert calls[0]['expected_boot'] == binding['expected_boot']
    assert calls[0]['configuration']['hold_policy']['drift'] == 2
    assert calls[0]['configuration']['hold_policy']['permit_explicit_enable'] == 1
    assert result['observation'] == {'test_only': True}


@pytest.mark.parametrize('fault', ['approval', 'startup', 'policy', 'export', 'trial'])
def test_failure_no_retry(prepared, monkeypatch, fault):
    root, _, _ = prepared
    calls = []
    def fail(*args, **kwargs):
        raise ValueError('injected failure')
    def trial(*args, **kwargs):
        calls.append('trial')
        if fault == 'trial': raise ValueError('injected trial failure')
        pytest.fail('Must not reach hardware boundary')
    monkeypatch.setattr(module, 'run_first_hold', trial)
    if fault == 'startup': monkeypatch.setattr(module, 'review_recovery_startup', fail)
    if fault == 'export': monkeypatch.setattr(module, '_read', fail)
    if fault == 'policy':
        path = root / 'docs/hold-r7-supported-pose-draft.json'
        config = json.loads(path.read_bytes())
        config['hold_policy']['drift'] = 5
        path.write_text(json.dumps(config))
    with pytest.raises(ValueError):
        module.run_r16_hold(root, startup_export_id='startup', key=b'k'*32,
                            authorized_powered_hold=fault != 'approval')
    assert calls == (['trial'] if fault == 'trial' else [])
