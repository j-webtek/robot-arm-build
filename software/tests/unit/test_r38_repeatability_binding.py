import importlib.util
from pathlib import Path
import pytest
from test_shoulder_repeatability_plan import frozen


@pytest.mark.parametrize('fault',[None,'hash','parameters'])
def test_model_binding_before_network(tmp_path,monkeypatch,fault):
    scripts=Path(__file__).resolve().parents[2]/'scripts'
    monkeypatch.syspath_prepend(str(scripts))
    spec=importlib.util.spec_from_file_location('r38_binding_test',scripts/'run_r38_repeatability.py')
    cli=importlib.util.module_from_spec(spec);spec.loader.exec_module(cli)
    monkeypatch.setattr(cli,'review_recovery_startup',lambda *a,**k:dict(expected_boot='ab'*16))
    from rocell.application import product_ghost_export_review as reader
    models=frozen()
    if fault=='hash':models['sha256']='00'*32
    if fault=='parameters':models['parameters']['constant'][0]+=1
    monkeypatch.setattr(reader,'_read',lambda *a:({'frozen_models':models},'verified-test-receipt'))
    if fault:
        with pytest.raises(ValueError):cli.preflight(tmp_path,'startup')
    else:
        binding,_,claim=cli.preflight(tmp_path,'startup')
        assert binding['frozen_models']==models
        assert not claim.exists()


def test_r38_changes_only_preparation_and_selection():
    root=Path(__file__).resolve().parents[2]/'.firmware-tools'
    def files(rev):
        return {p.name:p.read_bytes() for p in (root/f'configured-diagnostic-candidate-r{rev}/RoArm-M3_example').iterdir() if p.is_file()}
    old,new=files(37),files(38)
    assert old.keys()==new.keys()
    assert {n for n in old if old[n]!=new[n]}=={'characterization_prepare.h',
        'characterization_controller.h','characterization_smoke_board.h'}
    assert b'CharacterizationPattern::Repeatability' in new['characterization_smoke_board.h']
