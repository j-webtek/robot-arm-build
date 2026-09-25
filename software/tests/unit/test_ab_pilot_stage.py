import hashlib
import importlib.util
from pathlib import Path
import pytest


@pytest.mark.parametrize('variant,revision,selector',[
    ('control',39,'ABControl'),('compensated',40,'ABCandidate')])
def test_staging_is_fixed_and_refuses_overwrite(tmp_path,monkeypatch,variant,revision,selector):
    scripts=Path(__file__).resolve().parents[2]/'scripts'
    spec=importlib.util.spec_from_file_location('ab_stage_test',scripts/'stage_ab_pilot.py')
    stage=importlib.util.module_from_spec(spec);spec.loader.exec_module(stage)
    prefix='.firmware-tools/configured-diagnostic-candidate-r38/RoArm-M3_example/'
    old=tmp_path/prefix;old.mkdir(parents=True)
    source=tmp_path/'firmware/diagnostics';source.mkdir(parents=True)
    (tmp_path/'runs').mkdir()
    files={name:b'old' for name in stage.HEADERS}
    files['characterization_smoke_board.h']=b'CharacterizationPattern::Repeatability'
    files['preserved.h']=b'unchanged'
    for name,raw in files.items():(old/name).write_bytes(raw)
    for name in stage.HEADERS:(source/name).write_bytes(b'new')
    report=dict(status='COMPILED',source_hashes={prefix+n:hashlib.sha256(b).hexdigest() for n,b in files.items()})
    monkeypatch.setattr(stage,'_read',lambda *a:(report,'verified-fixture'))
    result=stage.stage(tmp_path,variant)
    assert stage.verify_export(Path(result))['valid']
    target=tmp_path/f'.firmware-tools/configured-diagnostic-candidate-r{revision}/RoArm-M3_example'
    assert (target/'characterization_smoke_board.h').read_text()=='CharacterizationPattern::'+selector
    assert (target/'preserved.h').read_bytes()==b'unchanged'
    with pytest.raises(FileExistsError):stage.stage(tmp_path,variant)
    (old/'preserved.h').write_bytes(b'tampered')
    with pytest.raises(ValueError,match='Pinned r38'):stage.stage(tmp_path,variant)
