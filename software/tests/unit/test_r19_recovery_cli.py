"""CLI routing tests: fake receipts, no controller access or private key reads."""
import importlib.util
from pathlib import Path
import sys

import pytest


@pytest.mark.parametrize('profile,revision', [('supported',16), ('six_count',19)])
def test_recovery_cli_binds_profile_before_key_or_network(monkeypatch, profile, revision):
    scripts = Path(__file__).resolve().parents[2] / 'scripts'
    monkeypatch.syspath_prepend(str(scripts))
    spec = importlib.util.spec_from_file_location('recovery_cli_test', scripts/'run_supported_recovery.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    calls = []
    def receipt(root, export, **kw):
        calls.append(kw)
        assert export == 'test-startup'
        assert kw == {'revision': revision}
        raise ValueError('Missing authorized installation')
    def forbidden(*a, **kw):
        pytest.fail('Private image or hardware touched before receipt')
    monkeypatch.setattr(module, 'review_recovery_startup', receipt)
    monkeypatch.setattr(module, 'load_image', forbidden)
    monkeypatch.setattr(module, 'run_supported_recovery', forbidden)
    monkeypatch.setattr(sys, 'argv', ['recovery', '--profile', profile,
        '--startup-export', 'test-startup', '--preflight-only'])
    with pytest.raises(ValueError, match='Missing authorized installation'):
        module.main()
    assert len(calls) == 1
