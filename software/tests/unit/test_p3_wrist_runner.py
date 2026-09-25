import importlib.util
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def runner(monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT/'scripts'))
    spec = importlib.util.spec_from_file_location('tested_p2_runner', ROOT/'scripts/run_p3_wrist.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_preflight_mode_never_opens_transport(runner, monkeypatch, tmp_path):
    monkeypatch.setattr(runner, 'preflight', lambda *args: (
        {'expected_boot':'ab'*16}, tmp_path, tmp_path/'claim.json', 'digest'))
    monkeypatch.setattr(runner, 'HoldHTTPReader', lambda *a: pytest.fail('Unexpected hardware access'))
    runner.main(['--startup-export','synthetic','--preflight-only'])
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize('wrong_boot', [False, True])
def test_live_runner_binds_profile_and_claim(runner, monkeypatch, tmp_path, wrong_boot):
    boot = 'ab'*16
    claim = tmp_path/'claim.json'
    monkeypatch.setattr(runner, 'preflight', lambda *args: (
        {'expected_boot':boot,'address':'synthetic'}, tmp_path, claim, 'digest'))
    monkeypatch.setattr(runner, 'HoldHTTPReader', lambda *a: lambda *a,**kw: b'ignored')
    monkeypatch.setattr(runner, 'decode_diagnostic_json', lambda *a,**kw: dict(
        instance_id='cd'*16 if wrong_boot else boot, state='IDLE', storage_fault=False))
    monkeypatch.setattr(runner, 'load_reviewed_key', lambda *a: b'test-key')
    monkeypatch.setattr(runner, 'CharacterizationHTTP', lambda *a,**kw: object())
    calls = []
    class Host:
        def __init__(self, client, **kwargs):
            assert claim.exists()
            assert kwargs['profile'] == 'P3' and kwargs['boot'] == boot
        def run_once(self):
            calls.append('write')
            raise TimeoutError('uncertain')
    monkeypatch.setattr(runner, 'LargePoseReliefHost', Host)
    with pytest.raises(ValueError if wrong_boot else TimeoutError):
        runner.main(['--startup-export','synthetic','--authorized-once'])
    assert calls == ([] if wrong_boot else ['write'])
    assert claim.exists() is not wrong_boot


def test_real_source_replay_and_claim_rejection(runner, monkeypatch, tmp_path):
    # Retained source evidence is independently replayed; no controller is read.
    monkeypatch.setattr(runner, 'review_recovery_startup', lambda root, ident, revision: (
        {'expected_boot':'ab'*16} if revision == 67 else pytest.fail('Wrong firmware binding')))
    exports = ROOT/'runs/wizard-exports'
    source = exports/runner.SOURCE
    assert source.is_dir(), 'Pinned P3E source export required for integration review'
    local = tmp_path/'runs/wizard-exports'/runner.SOURCE
    import shutil
    shutil.copytree(source, local)
    binding, _, claim, _ = runner.preflight(tmp_path, 'synthetic-startup')
    assert binding['expected_boot'] == 'ab'*16
    claim.touch()
    with pytest.raises(ValueError, match='already claimed'):
        runner.preflight(tmp_path, 'synthetic-startup')
