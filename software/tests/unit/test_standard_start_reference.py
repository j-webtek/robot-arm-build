from pathlib import Path
import shutil
import subprocess

import pytest

from rocell.application.fixed_pair_reanchor_record import export_fixed_pair_reanchor_fixture
from rocell.application.standard_start_reference import freeze_standard_start_reference


PLAN = {'schema': 'rocell.fixed_pair_reanchor_plan.v1',
        'target_goals': [2389, 1725], 'expected_positions': [2391, 1724]}


@pytest.fixture(scope='module')
def raw(tmp_path_factory):
    compiler = shutil.which('clang++')
    if not compiler:
        pytest.skip('Native compiler unavailable')
    root = Path(__file__).resolve().parents[2]
    target = tmp_path_factory.mktemp('reference-a') / 'owner.exe'
    build = subprocess.run([compiler, '-std=c++17',
                            str(root/'firmware/diagnostics/test_fixed_pair_reanchor_owner.cpp'),
                            '-o', str(target)], capture_output=True, text=True, timeout=30)
    assert build.returncode == 0, build.stderr
    run = subprocess.run([str(target), 'success'], capture_output=True, text=True, timeout=10)
    assert run.returncode == 0, run.stderr
    return bytes.fromhex(run.stdout.strip())


def test_reference_is_measured_encoder_checkpoint_not_park(tmp_path, raw):
    source = export_fixed_pair_reanchor_fixture(tmp_path, raw,
        expected_boot='ab'*16, plan=PLAN)
    saved, reference = freeze_standard_start_reference(tmp_path, Path(source).name,
        boot='ab'*16, plan=PLAN)
    assert Path(saved).is_dir()
    assert [j['goal'] for j in reference['joints'][1:3]] == [2389, 1725]
    assert [j['position'] for j in reference['joints'][1:3]] == [2391, 1724]
    assert reference['physical_park_verified'] is False
    assert reference['safe_to_replay_without_fresh_capture'] is False
    with pytest.raises(ValueError, match='boot mismatch'):
        freeze_standard_start_reference(tmp_path, Path(source).name,
            boot='cd'*16, plan=PLAN)
