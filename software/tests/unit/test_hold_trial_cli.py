"""CLI scope boundaries; no physical operations or real credential fixtures."""
import builtins
import importlib.util
import json
from pathlib import Path
import sys
import pytest


@pytest.fixture
def command(monkeypatch):
    scripts = Path(__file__).resolve().parents[2]/'scripts'
    monkeypatch.syspath_prepend(str(scripts))
    spec = importlib.util.spec_from_file_location('hold_trial_cli_test', scripts/'run_hold_r7.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize('arguments', [[], ['--authorized-powered-hold'],
    ['--authorized-powered-hold', '--expected-boot', '00'*16],
    ['--preflight-only', '--expected-boot', '00'*16]])
def test_scope_before_preflight(command, monkeypatch, arguments):
    monkeypatch.setattr(command, 'preflight', lambda *a: pytest.fail('Invalid scope reached preflight'))
    monkeypatch.setattr(sys, 'argv', ['hold.py', *arguments])
    with pytest.raises(SystemExit):
        command.main()


@pytest.mark.parametrize('supported', [False, True])
def test_preflight_no_key_or_trial_import(command, monkeypatch, capsys, supported):
    def preflight(root, *, supported_pose):
        assert supported_pose is supported
        return {}, b'fixture'
    monkeypatch.setattr(command, 'preflight', preflight)
    monkeypatch.setattr(command, 'read_hold_key', lambda *a: pytest.fail('Key extraction'))
    original = builtins.__import__
    def guarded(name, *args, **kwargs):
        assert name not in ('littlefs', 'rocell.application.hold_first_trial_run')
        return original(name, *args, **kwargs)
    monkeypatch.setattr(builtins, '__import__', guarded)
    monkeypatch.setattr(sys, 'argv', ['hold.py', '--preflight-only'] + (['--supported-pose'] if supported else []))
    command.main()
    result = json.loads(capsys.readouterr().out)
    assert result['status'] == 'LOCAL_HOLD_PREFLIGHT_VERIFIED'
    assert result['expected_boot'] == (command.SUPPORTED_BOOT if supported else command.BOOT)
    assert not any(result[k] for k in ('hardware_access', 'key_extracted', 'attempt_reserved', 'motion_authorized'))


@pytest.mark.parametrize('supported', [False, True])
def test_boot_from_other_profile_rejected(command, monkeypatch, supported):
    monkeypatch.setattr(command, 'preflight', lambda *a, **k: pytest.fail('Wrong boot reached preflight'))
    boot = command.BOOT if supported else command.SUPPORTED_BOOT
    monkeypatch.setattr(sys, 'argv', ['hold.py', '--authorized-powered-hold', '--expected-boot', boot]
                        + (['--supported-pose'] if supported else []))
    with pytest.raises(SystemExit):
        command.main()
