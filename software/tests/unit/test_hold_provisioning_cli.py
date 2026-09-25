"""CLI authority boundary checks; no live images or hardware in fixtures."""
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
    spec = importlib.util.spec_from_file_location('hold_provision_cli_test', scripts/'provision_hold_r7.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize('arguments', [[], ['--authorized-provision-and-startup'],
    ['--authorized-provision-and-startup', '--candidate-sha256', '0'*64],
    ['--preflight-only', '--candidate-sha256', '0'*64]])
def test_missing_or_wrong_scope_never_enters_preflight(command, monkeypatch, arguments):
    def forbidden(*args): raise AssertionError('Invalid CLI must stop before preflight')
    monkeypatch.setattr(command, 'preflight', forbidden)
    monkeypatch.setattr(sys, 'argv', ['provision.py', *arguments])
    with pytest.raises(SystemExit): command.main()


def test_local_only_path_cannot_import_device_or_extract_key(command, monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(command, 'preflight', lambda root: (tmp_path, b'source', b'candidate', b'policy', None))
    def forbidden(*args): raise AssertionError('No device or key operations in local preflight')
    monkeypatch.setattr(command, 'read_hold_key', forbidden)
    monkeypatch.setattr(command, 'run_hold_provisioning', forbidden)
    original = builtins.__import__
    def guarded(name, *args, **kwargs):
        assert name.split('.')[0] not in ('esptool', 'serial', 'littlefs')
        return original(name, *args, **kwargs)
    monkeypatch.setattr(builtins, '__import__', guarded)
    monkeypatch.setattr(sys, 'argv', ['provision.py', '--preflight-only'])
    command.main()
    result = json.loads(capsys.readouterr().out)
    assert result['status'] == 'LOCAL_PREFLIGHT_VERIFIED'
    assert not any(result[k] for k in ('hardware_access','journal_reserved','key_created','provisioning_authorized'))
