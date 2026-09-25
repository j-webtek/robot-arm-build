"""CLI admission failures must precede private-image or device-library access."""
import builtins
import importlib.util
from pathlib import Path
import pytest


@pytest.fixture
def cli(monkeypatch):
    root = Path(__file__).resolve().parents[2]
    monkeypatch.syspath_prepend(str(root/'scripts'))
    spec = importlib.util.spec_from_file_location('observed_install_cli',
        root/'scripts/install_observed_pose_settings.py')
    module = importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    monkeypatch.setattr(module, 'load_image', lambda *a: pytest.fail('Unexpected private-image access'))
    original = builtins.__import__
    def guarded(name, *a, **kw):
        if name in ('serial','esptool'): pytest.fail('Unexpected hardware-library import')
        return original(name,*a,**kw)
    monkeypatch.setattr(builtins, '__import__', guarded)
    return module


def test_missing_execution_choice(cli):
    with pytest.raises(SystemExit) as error:
        cli.main(['--stage-export','unused','--candidate-sha256','a'*64])
    assert error.value.code == 2


@pytest.mark.parametrize('mode', ['--preflight-only','--authorized-filesystem-install-and-startup'])
def test_missing_r21_receipt_stops_first(cli, monkeypatch, mode):
    def missing(*a, **kw):
        assert kw['revision'] == 21
        raise ValueError('Synthetic missing r21 installation')
    monkeypatch.setattr(cli,'review_pair_installation',missing)
    with pytest.raises(ValueError,match='missing r21'):
        cli.main(['--stage-export','unused','--candidate-sha256','a'*64,mode])
