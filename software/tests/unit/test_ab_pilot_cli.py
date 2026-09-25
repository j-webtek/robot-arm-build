import importlib.util
import json
import sys
from pathlib import Path
import pytest
from test_shoulder_repeatability_plan import frozen


@pytest.fixture
def cli(monkeypatch):
    scripts = Path(__file__).resolve().parents[2]/'scripts'
    monkeypatch.syspath_prepend(str(scripts))
    spec = importlib.util.spec_from_file_location('ab_cli_test', scripts/'run_ab_pilot.py')
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize('variant',['control','compensated'])
def test_requires_actual_installation_journal(cli,tmp_path,variant):
    # Adding a reviewed profile is not evidence that the image was installed.
    from rocell.application.physical_onboarding_durability import PhysicalOnboardingDurabilityError
    with pytest.raises(PhysicalOnboardingDurabilityError, match='regular file'):
        cli.preflight(tmp_path, 'r38-startup', variant)


@pytest.mark.parametrize('fault', [None,'hash','parameters','reserved'])
def test_local_binding(cli,tmp_path,monkeypatch,fault):
    def startup(*a,**kw):
        assert kw['revision']==39
        return dict(expected_boot='ab'*16)
    monkeypatch.setattr(cli,'review_recovery_startup',startup)
    models=frozen()
    if fault=='hash':models['sha256']='00'*32
    if fault=='parameters':models['parameters']['constant'][0]+=1
    monkeypatch.setattr(cli,'_read',lambda *a:({'frozen_models':models},'test-receipt'))
    exports=tmp_path/'runs/wizard-exports';exports.mkdir(parents=True)
    claim=exports/('r39-capture-'+'ab'*16+'.json')
    if fault=='reserved':claim.write_text('existing')
    if fault:
        with pytest.raises(ValueError):cli.preflight(tmp_path,'test','control')
    else:
        binding,_,path=cli.preflight(tmp_path,'test','control')
        assert binding['frozen_models']==models and path==claim and not claim.exists()


def test_preflight_no_key_network_or_claim(cli,tmp_path,monkeypatch,capsys):
    claim=tmp_path/'claim.json'
    monkeypatch.setattr(cli,'preflight',lambda *a:({},tmp_path,claim))
    def forbidden(*a,**kw):pytest.fail('Live operation during preflight')
    monkeypatch.setattr(cli,'load_reviewed_key',forbidden)
    monkeypatch.setattr(cli,'CharacterizationHTTP',forbidden)
    monkeypatch.setattr(sys,'argv',['run','--variant','control','--startup-export','test','--preflight-only'])
    cli.main()
    assert not claim.exists() and 'LOCAL_BINDING_VERIFIED' in capsys.readouterr().out


@pytest.mark.parametrize('variant',['control','compensated'])
def test_claim_before_connection_and_no_replay(cli,tmp_path,monkeypatch,variant):
    claim=tmp_path/'claim.json'
    binding=dict(expected_boot='ab'*16,address='127.0.0.1',frozen_models=frozen())
    monkeypatch.setattr(cli,'preflight',lambda *a:(binding,tmp_path,claim))
    monkeypatch.setattr(cli,'load_reviewed_key',lambda *a:b'k'*32)
    def connection(*a,**kw):
        assert json.loads(claim.read_text())['variant']==variant
        return object()
    monkeypatch.setattr(cli,'CharacterizationHTTP',connection)
    class Runner:
        def __init__(self,*a,**kw):
            assert kw['variant']==variant and kw['frozen_models']==binding['frozen_models']
            assert kw['recovery_factory']('cd'*32).boot==binding['expected_boot']
        def run(self,**kw):
            assert kw==dict(motion_admitted=True)
            return dict(export_path='offline-test',report=dict(status='INCONCLUSIVE'))
    monkeypatch.setattr(cli,'ABRunner',Runner)
    monkeypatch.setattr(sys,'argv',['run','--variant',variant,'--startup-export','test',
        '--authorized-three-leg-campaign-clearance-confirmed'])
    with pytest.raises(SystemExit) as stopped:cli.main()
    assert stopped.value.code==1 and claim.exists()
    with pytest.raises(FileExistsError):cli.main()
