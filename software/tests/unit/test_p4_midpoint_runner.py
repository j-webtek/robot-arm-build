import importlib.util
from pathlib import Path
import pytest

ROOT=Path(__file__).resolve().parents[2]


@pytest.fixture
def runner(monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT/'scripts'))
    spec=importlib.util.spec_from_file_location('p4_midpoint_runner',
        ROOT/'scripts/run_p4_midpoint_campaign.py')
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_preflight_only_never_opens_transport(runner,monkeypatch,tmp_path):
    monkeypatch.setattr(runner,'preflight',lambda *args: (
        {'expected_boot':'ab'*16},tmp_path,tmp_path/'claim.json'))
    monkeypatch.setattr(runner,'HoldHTTPReader',lambda *a: pytest.fail('Unexpected hardware access'))
    runner.main(['--startup-export','synthetic','--preflight-only'])
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize('wrong_boot',[False,True])
def test_one_use_claim_precedes_host(runner,monkeypatch,tmp_path,wrong_boot):
    boot='ab'*16;claim=tmp_path/'claim.json';calls=[]
    monkeypatch.setattr(runner,'preflight',lambda *args: (
        {'expected_boot':boot,'address':'synthetic'},tmp_path,claim))
    monkeypatch.setattr(runner,'HoldHTTPReader',lambda *a: lambda *a,**kw:b'ignored')
    monkeypatch.setattr(runner,'decode_diagnostic_json',lambda *a,**kw:dict(
        instance_id='cd'*16 if wrong_boot else boot,state='IDLE',storage_fault=False))
    monkeypatch.setattr(runner,'load_reviewed_key',lambda *a:b'test-key')
    monkeypatch.setattr(runner,'CharacterizationHTTP',lambda *a,**kw:object())
    class Host:
        def __init__(self,client,**kwargs):
            assert claim.exists() and kwargs['boot']==boot
        def run_once(self):
            calls.append('run')
            raise TimeoutError('delivery uncertain')
    monkeypatch.setattr(runner,'P4MidpointHost',Host)
    with pytest.raises(ValueError if wrong_boot else TimeoutError):
        runner.main(['--startup-export','synthetic','--authorized-once'])
    assert calls==([] if wrong_boot else ['run'])
    assert claim.exists() is not wrong_boot
