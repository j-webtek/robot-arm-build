import importlib.util
from pathlib import Path

import pytest

from rocell.application.separated_pair_mapping_batch import plan_separated_mapping_batch


@pytest.fixture
def cli(monkeypatch):
    scripts=Path(__file__).resolve().parents[2]/'scripts'
    monkeypatch.syspath_prepend(str(scripts))
    spec=importlib.util.spec_from_file_location('separated_mapping_batch_cli_test',
                                                scripts/'run_separated_pair_mapping_batch.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize('fault',[None,'plan','reserved','pose_reserved'])
def test_preflight_binds_r49_plan_and_one_use_boot(cli,tmp_path,monkeypatch,fault):
    boot='ab'*16
    monkeypatch.setattr(cli,'review_recovery_startup',lambda *args,**kwargs:
                        {'expected_boot':boot,'address':'127.0.0.1'})
    saved=plan_separated_mapping_batch()
    if fault=='plan':
        saved=dict(saved);saved['revision']=48
    monkeypatch.setattr(cli,'_read',lambda *args:(saved,'verified'))
    exports=tmp_path/'runs/wizard-exports';exports.mkdir(parents=True)
    if fault=='reserved':(exports/f'r49-capture-{boot}.json').write_text('{}')
    if fault=='pose_reserved':(exports/f'pose-observation-{boot}.json').write_text('{}')
    if fault:
        with pytest.raises(ValueError):cli.preflight(tmp_path,'startup')
    else:
        binding,root,claim=cli.preflight(tmp_path,'startup')
        assert binding['mapping_plan']==plan_separated_mapping_batch()
        assert root==exports and claim.name==f'r49-capture-{boot}.json'
