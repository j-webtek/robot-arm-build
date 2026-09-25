"""Local-only CLI boundary tests; no staging or USB access."""
import builtins
import importlib.util
from pathlib import Path
import sys

import pytest


def module():
    path = Path(__file__).resolve().parents[2] / 'scripts/provision_startup_r6.py'
    spec = importlib.util.spec_from_file_location('startup_provisioning_cli', path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def test_preflight_exits_before_key_or_device_imports(monkeypatch, capsys, tmp_path):
    cli = module()
    monkeypatch.setattr(cli, 'preflight', lambda root: (tmp_path, b'source', b'policy', None))
    def forbidden(*args, **kwargs): raise AssertionError('Forbidden preflight effect')
    monkeypatch.setattr(cli.secrets, 'token_bytes', forbidden)
    original = builtins.__import__
    def guarded(name, *args, **kwargs):
        if name.split('.')[0] in ('esptool', 'serial', 'littlefs'): forbidden()
        return original(name, *args, **kwargs)
    monkeypatch.setattr(builtins, '__import__', guarded)
    monkeypatch.setattr(sys, 'argv', ['provision_startup_r6.py', '--preflight-only'])
    cli.main()
    assert 'LOCAL_PREFLIGHT_VERIFIED' in capsys.readouterr().out
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize('args', [[], ['--authorized-provision-and-startup'],
    ['--preflight-only', '--candidate-sha256', 'a'*64],
    ['--authorized-stage-private', '--candidate-sha256', 'a'*64]])
def test_explicit_modes_reject_ambiguous_invocation(monkeypatch, args):
    cli = module()
    def forbidden(root): raise AssertionError('No preflight on invalid invocation')
    monkeypatch.setattr(cli, 'preflight', forbidden)
    monkeypatch.setattr(sys, 'argv', ['provision_startup_r6.py', *args])
    with pytest.raises(SystemExit) as error: cli.main()
    assert error.value.code == 2
