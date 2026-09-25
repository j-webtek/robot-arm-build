import importlib.util
import sys
from pathlib import Path
import pytest


@pytest.fixture(params=[34,35,36,37,38])
def cli(monkeypatch,request):
    scripts=Path(__file__).resolve().parents[2]/'scripts'
    monkeypatch.syspath_prepend(str(scripts))
    filename='run_r34_smoke.py' if request.param==34 else f'run_r{request.param}_matched.py'
    if request.param==37:filename='run_r37_matrix.py'
    if request.param==38:filename='run_r38_repeatability.py'
    spec=importlib.util.spec_from_file_location('smoke_cli_test',scripts/filename)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    module.test_revision=request.param
    return module


def test_reserved_boot_rejected_before_key_or_network(cli,tmp_path,monkeypatch):
    monkeypatch.setattr(cli,'review_recovery_startup',lambda *a,**k:dict(expected_boot='ab'*16))
    exports=tmp_path/'runs/wizard-exports';exports.mkdir(parents=True)
    (exports/(f'r{cli.test_revision}-capture-'+'ab'*16+'.json')).write_text('existing')
    with pytest.raises(ValueError,match='reserved'):cli.preflight(tmp_path,'startup')


def test_preflight_has_no_key_network_or_reservation(cli,tmp_path,monkeypatch,capsys):
    claim=tmp_path/'claim.json'
    monkeypatch.setattr(cli,'preflight',lambda *a:({},tmp_path,claim))
    def forbidden(*a,**k):pytest.fail('Live operation during preflight')
    monkeypatch.setattr(cli,'load_reviewed_key',forbidden)
    monkeypatch.setattr(cli,'CharacterizationHTTP',forbidden)
    monkeypatch.setattr(sys,'argv',['run','--startup-export','test','--preflight-only'])
    cli.main()
    assert not claim.exists()
    assert 'LOCAL_BINDING_VERIFIED' in capsys.readouterr().out


def test_live_branch_reserves_before_transport_and_selects_runner(cli,tmp_path,monkeypatch):
    import json
    claim=tmp_path/'claim.json'
    binding=dict(expected_boot='ab'*16,address='127.0.0.1')
    if cli.test_revision==38:
        from test_shoulder_repeatability_plan import frozen
        binding['frozen_models']=frozen()
    monkeypatch.setattr(cli,'preflight',lambda *a:(binding,tmp_path,claim))
    monkeypatch.setattr(cli,'load_reviewed_key',lambda *a:b'k'*32)
    def transport(*a,**k):
        assert claim.exists()
        assert json.loads(claim.read_text())['boot']==binding['expected_boot']
        return object()
    monkeypatch.setattr(cli,'CharacterizationHTTP',transport)
    class Runner:
        def __init__(self,*a,**k):
            if cli.test_revision==38:assert k['frozen_models']==binding['frozen_models']
            if cli.test_revision>=35:
                reader=k['recovery_factory']('cd'*32)
                assert reader.boot==binding['expected_boot'] and reader.campaign=='cd'*32
            else:assert 'recovery_factory' not in k
        def run(self,**k):
            assert k==dict(motion_admitted=True)
            return dict(export_path='fake-offline-export',report=dict(status='INCONCLUSIVE'))
    runner='SmokeRunner' if cli.test_revision==34 else 'MatrixRunner' if cli.test_revision==37 else 'MatchedRunner'
    if cli.test_revision==38:runner='RepeatabilityRunner'
    monkeypatch.setattr(cli,runner,Runner)
    flag='--authorized-one-movement-clearance-confirmed' if cli.test_revision==34 else '--authorized-twelve-leg-campaign-clearance-confirmed'
    if cli.test_revision==38:flag='--authorized-six-leg-campaign-clearance-confirmed'
    monkeypatch.setattr(sys,'argv',['run','--startup-export','test',flag])
    with pytest.raises(SystemExit) as stopped:cli.main()
    assert stopped.value.code==1 and claim.exists()
    with pytest.raises(FileExistsError):cli.main()
