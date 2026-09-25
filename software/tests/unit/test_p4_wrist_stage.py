import importlib.util
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[2]


def test_exact_specialization_and_tamper_rejection():
    spec = importlib.util.spec_from_file_location('t4_stage', ROOT/'scripts/stage_r71_p4_wrist.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    base = ROOT/'.firmware-tools/configured-diagnostic-candidate-r70/RoArm-M3_example'
    files = {p.name:p.read_bytes() for p in base.iterdir() if p.is_file()}
    result = module.specialize(files)
    candidate = ROOT/'.firmware-tools/configured-diagnostic-candidate-r71/RoArm-M3_example'
    assert result == {p.name:p.read_bytes() for p in candidate.iterdir() if p.is_file()}
    assert {name for name in files if files[name] != result[name]} == {
        'large_pose_relief_policy.h','large_pose_relief_owner.h',
        'large_pose_relief_routes.h','characterization_board_services.h'}
    modified = dict(files)
    modified['large_pose_relief_owner.h'] = files['large_pose_relief_owner.h'].replace(b'RCP4ELBW01', b'WRONGTOKEN')
    with pytest.raises(ValueError, match='Unexpected source'):
        module.specialize(modified)
    with pytest.raises(ValueError, match='Unexpected source'):
        module.specialize(result)
