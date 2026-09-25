import importlib.util,json,sys
from pathlib import Path
import pytest
from test_shoulder_repeatability_plan import frozen
from rocell.application.next_compensation_validation import draft


@pytest.fixture
def cli(monkeypatch):
    scripts=Path(__file__).resolve().parents[2]/'scripts';monkeypatch.syspath_prepend(str(scripts))
    spec=importlib.util.spec_from_file_location('next_validation_cli_test',scripts/'run_next_validation.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module


def test_r41_requires_actual_installation(cli,tmp_path):
    from rocell.application.physical_onboarding_durability import PhysicalOnboardingDurabilityError
    with pytest.raises(PhysicalOnboardingDurabilityError):
        cli.preflight(tmp_path,'startup','forward_repeat')


@pytest.mark.parametrize('fault',[None,'hash','manifest','reserved'])
def test_offline_binding(cli,tmp_path,monkeypatch,fault):
    monkeypatch.setattr(cli,'review_recovery_startup',lambda *a,**k:
        dict(expected_boot='ab'*16,address='127.0.0.1'))
    models=frozen();plan=draft(frozen=models,bounds=[[0,4095] for _ in range(7)],
        installed_goals=(2378,1736),installed_positions=(2387,1730))
    if fault=='hash':plan['frozen_model_sha256']='00'*32
    if fault=='manifest':plan['forward_repeat']['manifest']['goals'][-1][0]+=1
    def read(root,ident,name):
        return (plan if name=='attachment-next-validation-plan.json' else
                {'frozen_models':models}),'verified'
    monkeypatch.setattr(cli,'_read',read)
    exports=tmp_path/'runs/wizard-exports';exports.mkdir(parents=True)
    claim=exports/('r41-capture-'+'ab'*16+'.json')
    if fault=='reserved':claim.write_text('used')
    if fault:
        with pytest.raises(ValueError):cli.preflight(tmp_path,'startup','forward_repeat')
    else:
        binding,_,path=cli.preflight(tmp_path,'startup','forward_repeat')
        assert binding['frozen_models']==models and path==claim


def test_live_claim_precedes_connection(cli,tmp_path,monkeypatch):
    claim=tmp_path/'claim.json';binding=dict(expected_boot='ab'*16,address='127.0.0.1',
        frozen_models=frozen(),plan_export='plan')
    monkeypatch.setattr(cli,'preflight',lambda *a:(binding,tmp_path,claim))
    monkeypatch.setattr(cli,'load_reviewed_key',lambda *a:b'k'*32)
    def connect(*a,**k):assert json.loads(claim.read_text())['variant']=='forward_repeat';return object()
    monkeypatch.setattr(cli,'CharacterizationHTTP',connect)
    class Runner:
        def __init__(self,*a,**k):assert k['variant']=='forward_repeat'
        def run(self,**k):return dict(export_path='test',report=dict(status='INCONCLUSIVE'))
    monkeypatch.setattr(cli,'NextValidationRunner',Runner)
    monkeypatch.setattr(sys,'argv',['run','--variant','forward_repeat','--startup-export','startup',
        '--authorized-fixed-campaign-clearance-confirmed'])
    with pytest.raises(SystemExit):cli.main()
    assert claim.exists()
    with pytest.raises(FileExistsError):cli.main()


def test_heldout_candidate_binds_r44_and_current_two_leg_plan(cli,tmp_path,monkeypatch):
    monkeypatch.setattr(cli,'review_recovery_startup',lambda *a,**k:
        dict(expected_boot='cd'*16,address='127.0.0.1'))
    models=frozen()
    heldout=dict(frozen_model_sha256=models['sha256'],candidate=dict(
        manifest=dict(goals=[[2377,1737],[2388,1726]])))
    def read(root,ident,name):
        if name=='attachment-heldout-pair-plan.json':
            assert ident==cli.HELDOUT_PLAN
            return heldout,'verified'
        return {'frozen_models':models},'verified'
    monkeypatch.setattr(cli,'_read',read)
    exports=tmp_path/'runs/wizard-exports';exports.mkdir(parents=True)
    binding,_,claim=cli.preflight(tmp_path,'startup','heldout_candidate')
    assert binding['plan_export']==cli.HELDOUT_PLAN
    assert claim.name=='r44-capture-'+'cd'*16+'.json'


def test_pose_observation_reservation_blocks_same_boot_campaign(cli,tmp_path,monkeypatch):
    boot='ef'*16
    monkeypatch.setattr(cli,'review_recovery_startup',lambda *a,**k:
        dict(expected_boot=boot,address='127.0.0.1'))
    exports=tmp_path/'runs/wizard-exports';exports.mkdir(parents=True)
    (exports/f'pose-observation-{boot}.json').write_text('{}')
    with pytest.raises(ValueError,match='reserved by pose observation'):
        cli.preflight(tmp_path,'startup','heldout_candidate')


def test_second_heldout_candidate_binds_r46_and_frozen_plan(cli,tmp_path,monkeypatch):
    monkeypatch.setattr(cli,'review_recovery_startup',lambda *a,**k:
        dict(expected_boot='12'*16,address='127.0.0.1'))
    models=frozen()
    plan=dict(frozen_model_sha256=models['sha256'],candidate=dict(
        manifest=dict(goals=[[2377,1737],[2389,1725],[2378,1736]])))
    def read(root,ident,name):
        if name=='attachment-second-heldout-pair-plan.json':
            assert ident==cli.SECOND_HELDOUT_PLAN
            return plan,'verified'
        return {'frozen_models':models},'verified'
    monkeypatch.setattr(cli,'_read',read)
    exports=tmp_path/'runs/wizard-exports';exports.mkdir(parents=True)
    binding,_,claim=cli.preflight(tmp_path,'startup','second_heldout_candidate')
    assert binding['plan_export']==cli.SECOND_HELDOUT_PLAN
    assert claim.name=='r46-capture-'+'12'*16+'.json'
