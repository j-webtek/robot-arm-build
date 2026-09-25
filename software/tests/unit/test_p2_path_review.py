from pathlib import Path
import shutil
import subprocess

import pytest

from rocell.application.p2_path_review import review_p2_path

ROOT = Path(__file__).resolve().parents[2]
MODEL = ROOT/'models/roarm_m3/roarm_m3_kinematic_40dbd84.urdf'


@pytest.fixture(scope='module')
def raw(tmp_path_factory):
    compiler = shutil.which('clang++')
    if not compiler:
        pytest.skip('Native compiler unavailable')
    executable = tmp_path_factory.mktemp('p2-review')/'owner.exe'
    subprocess.run([compiler, '-std=c++17', str(ROOT/'firmware/diagnostics/test_large_pose_relief_owner.cpp'),
                    '-o', str(executable)], check=True, capture_output=True, timeout=30)
    output = subprocess.run([str(executable), 'success'], check=True,
                            capture_output=True, text=True, timeout=10)
    return bytes.fromhex(output.stdout.strip())


def test_timing_order_changes_minimum_height(raw):
    result = review_p2_path(raw, expected_boot='ab'*16, model_path=MODEL)
    initial_z = result['start_tcp_mm'][2]
    assert result['independent_progress']['minimum_tcp_z_mm'] < initial_z-3
    assert result['shoulder_first']['minimum_tcp_z_mm'] == pytest.approx(initial_z)
    assert result['p2l_tcp_mm'][2] > initial_z+15
    assert result['proposed_p2l_goals'] == [2047,2283,1831,2842,1719,2040,2047]
    assert result['proposed_p2_goals'] == [2047,2283,1831,2842,1785,2040,2047]
    assert result['independent_progress']['sample_count'] == 41**2
    assert not result['physical_clearance_verified']
    assert not result['movement_authorized']


def test_wrong_boot_and_corrupt_record_rejected(raw):
    with pytest.raises(ValueError, match='identity mismatch'):
        review_p2_path(raw, expected_boot='cd'*16, model_path=MODEL)
    with pytest.raises(ValueError, match='framing'):
        review_p2_path(raw[:-1], expected_boot='ab'*16, model_path=MODEL)


@pytest.mark.parametrize('resolution', [True, 0, 1, 201, 2.5])
def test_invalid_grid_rejected(resolution):
    with pytest.raises(ValueError, match='grid resolution'):
        review_p2_path(b'', expected_boot='ab'*16, model_path=MODEL, subdivisions=resolution)
