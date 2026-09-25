from pathlib import Path
import shutil
import subprocess

import pytest

from rocell.application.park_reanchor_plan import OFFSET_GOALS
from rocell.application.park_reanchor_record import (
    RECORD_BYTES, assess_park_reanchor_record, decode_park_reanchor_record,
    export_park_reanchor_record, replay_park_reanchor_record,
)


@pytest.fixture(scope='module')
def binary(tmp_path_factory):
    compiler = shutil.which('clang++')
    if not compiler:
        pytest.skip('Native compiler unavailable')
    root = Path(__file__).resolve().parents[2]
    target = tmp_path_factory.mktemp('park-reanchor-record') / 'test.exe'
    built = subprocess.run(
        [compiler, '-std=c++17', '-Wall', '-Wextra', '-Werror',
         str(root / 'firmware/diagnostics/test_park_reanchor_owner.cpp'),
         '-o', str(target)], capture_output=True, text=True, timeout=30,
    )
    assert built.returncode == 0, built.stderr
    return target


def native_record(binary, mode):
    ran = subprocess.run([str(binary), mode], capture_output=True, text=True,
                         timeout=10)
    assert ran.returncode == 0, ran.stderr
    return bytes.fromhex(ran.stdout.strip())


def plan():
    return {'schema': 'rocell.park_reanchor_plan.v1',
            'target_goals': [2389, 1725], 'source_goals': list(OFFSET_GOALS)}


def test_native_success_record_assesses_joint_return(binary):
    raw = native_record(binary, 'success')
    assert len(raw) == RECORD_BYTES
    assessed = assess_park_reanchor_record(raw, expected_boot='00'*16, plan=plan())
    assert assessed['status'] == 'MEASURED_RETURN'
    assert assessed['actual_position_delta'] == [4, -5]
    assert assessed['continuation_authorized'] is False
    assert assessed['physical_clearance_proven'] is False


def test_native_timeout_record_remains_fault(binary):
    raw = native_record(binary, 'timeout')
    assessed = assess_park_reanchor_record(raw, expected_boot='00'*16, plan=plan())
    assert assessed['status'] == 'FAULT_RECORDED'
    assert assessed['fault'] == 'TIMEOUT'
    assert assessed['reference_pose_verified'] is False


def test_rejects_corrupt_framing_and_source(binary):
    raw = native_record(binary, 'success')
    with pytest.raises(ValueError):
        decode_park_reanchor_record(raw[:-1])
    with pytest.raises(ValueError):
        assess_park_reanchor_record(raw, expected_boot='11'*16, plan=plan())


@pytest.mark.parametrize('mode,status', [
    ('success', 'MEASURED_RETURN'), ('timeout', 'FAULT_RECORDED'),
])
def test_export_replay_preserves_success_or_fault(binary, tmp_path, mode, status):
    raw = native_record(binary, mode)
    saved = export_park_reanchor_record(tmp_path, raw, expected_boot='00'*16,
                                        plan=plan())
    replayed = replay_park_reanchor_record(tmp_path, Path(saved).name,
                                           expected_boot='00'*16, plan=plan())
    assert replayed['status'] == status
