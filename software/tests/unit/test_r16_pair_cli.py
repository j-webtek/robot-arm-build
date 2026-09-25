"""CLI mode separation with inert adapters; no hardware or private data."""
import hashlib
import importlib.util
from pathlib import Path
import sys
import types
import pytest


@pytest.fixture
def cli(monkeypatch):
    scripts = Path(__file__).resolve().parents[2] / 'scripts'
    monkeypatch.syspath_prepend(str(scripts))
    spec = importlib.util.spec_from_file_location('test_r16_pair_cli_module', scripts/'run_r16_pair.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize('args', [[], ['--prepare-only'], ['--preflight-only'],
    ['--prepare-only','--hold-export','hold','--preparation-export','prep'],
    ['--authorized-powered-pair','--hold-export','hold'],
    ['--preflight-only','--authorized-powered-pair','--preparation-export','prep']])
def test_invalid_modes_do_not_load_private_material(cli, monkeypatch, args):
    monkeypatch.setattr(cli, 'load_image', lambda *a: pytest.fail('Unexpected private access'))
    with pytest.raises(SystemExit): cli.main(['--startup-export','startup']+args)


def test_prepare_is_offline(cli, monkeypatch, capsys):
    monkeypatch.setattr(cli, 'load_image', lambda *a: pytest.fail('Unexpected private access'))
    monkeypatch.setattr(cli, 'prepare_r16_pair', lambda root, **k: dict(prepared=k))
    cli.main(['--startup-export','startup','--prepare-only','--hold-export','hold'])
    assert 'prepared' in capsys.readouterr().out


@pytest.mark.parametrize('mode', ['preflight', 'live', 'bad_image'])
def test_key_only_extracted_for_live(cli, monkeypatch, capsys, mode):
    calls=[]
    image=b'x'*0x160000
    monkeypatch.setattr(cli, 'CANDIDATE', hashlib.sha256(image).hexdigest())
    monkeypatch.setattr(cli, 'review_r16_pair', lambda *a: (
        dict(expected_boot='12'*16),dict(preparation=dict(illustrative_targets=[2908,2902]))))
    monkeypatch.setattr(cli, 'check_private_acl', lambda *a: calls.append('acl'))
    monkeypatch.setattr(cli, 'load_image', lambda *a: b'bad' if mode=='bad_image' else image)
    fake=types.ModuleType('littlefs')
    fake.__file__=str(Path(cli.__file__).resolve().parents[1]/'.firmware-tools/littlefs-review/littlefs/__init__.py')
    monkeypatch.setitem(sys.modules,'littlefs',fake)
    monkeypatch.setattr(cli, 'read_hold_key', lambda *a: calls.append('key') or b'k'*32)
    monkeypatch.setattr(cli, 'run_r16_pair', lambda *a,**k: calls.append('trial') or {'test_only':True})
    modeflag='--preflight-only' if mode=='preflight' else '--authorized-powered-pair'
    args=['--startup-export','startup',modeflag,'--preparation-export','prep']
    # The CLI adds the pinned import directory only in live mode.
    monkeypatch.setattr(sys,'path',list(sys.path))
    if mode=='bad_image':
        with pytest.raises(ValueError): cli.main(args)
    else: cli.main(args)
    assert calls == (['acl','key','trial'] if mode=='live' else ['acl'])
