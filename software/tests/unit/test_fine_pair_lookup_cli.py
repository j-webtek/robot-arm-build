import importlib.util
from pathlib import Path
import pytest

from rocell.application.fine_pair_lookup_validation import plan_fine_lookup_validation


@pytest.fixture
def cli(monkeypatch):
    scripts=Path(__file__).resolve().parents[2]/'scripts';monkeypatch.syspath_prepend(str(scripts))
    spec=importlib.util.spec_from_file_location('fine_lookup_cli_test',scripts/'run_fine_pair_lookup_validation.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module


@pytest.mark.parametrize('fault',[None,'plan','reserved','pose_reserved'])
def test_preflight_binds_r50_plan_and_one_use_boot(cli,tmp_path,monkeypatch,fault):
    boot='ab'*16;monkeypatch.setattr(cli,'review_recovery_startup',lambda *a,**k:
        {'expected_boot':boot,'address':'127.0.0.1'})
    saved=plan_fine_lookup_validation()
    if fault=='plan':saved=dict(saved);saved['revision']=49
    monkeypatch.setattr(cli,'_read',lambda *a:(saved,'verified'))
    exports=tmp_path/'runs/wizard-exports';exports.mkdir(parents=True)
    if fault=='reserved':(exports/f'r50-capture-{boot}.json').write_text('{}')
    if fault=='pose_reserved':(exports/f'pose-observation-{boot}.json').write_text('{}')
    if fault:
        with pytest.raises(ValueError):cli.preflight(tmp_path,'startup')
    else:
        binding,root,claim=cli.preflight(tmp_path,'startup')
        assert binding['mapping_plan']==plan_fine_lookup_validation()
        assert root==exports and claim.name==f'r50-capture-{boot}.json'
