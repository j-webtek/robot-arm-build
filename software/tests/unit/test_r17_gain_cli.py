import importlib.util
import json
from pathlib import Path
import sys
import pytest


@pytest.mark.parametrize('capture', [False, True])
def test_gain_cli_binds_r17_and_only_captures_explicitly(monkeypatch, capsys, capture):
    path = Path(__file__).resolve().parents[2]/'scripts/capture_r17_gains.py'
    spec = importlib.util.spec_from_file_location('gain_cli_test', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    calls = []
    def review(root, ident, *, revision):
        assert ident == 'startup' and revision == 17
        return dict(address='192.168.0.225', expected_boot='11'*16)
    def caps(**kwargs):
        calls.append('capabilities')
        assert kwargs == dict(address='192.168.0.225', expected_boot='11'*16)
    def acquire(root, **kwargs):
        calls.append('capture')
        assert kwargs == dict(address='192.168.0.225', expected_boot='11'*16)
        return dict(test_capture=True)
    monkeypatch.setattr(module, 'review_recovery_startup', review)
    monkeypatch.setattr(module, 'read_pair_capabilities', caps)
    monkeypatch.setattr(module, 'capture_gain', acquire)
    monkeypatch.setattr(sys, 'argv', ['capture', '--startup-export', 'startup',
                                   '--capture' if capture else '--preflight-only'])
    module.main()
    result = json.loads(capsys.readouterr().out)
    assert calls == (['capabilities','capture'] if capture else [])
    if not capture:
        assert result['hardware_access'] is False
        assert result['motion_authorized'] is False
        assert result['gain_changes_authorized'] is False
