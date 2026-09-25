from pathlib import Path
import shutil
import subprocess

import pytest

from rocell.application.park_step_record import (
    RECORD_BYTES, assess_park_step_record, decode_park_step_record,
)


@pytest.fixture(scope='module')
def raw(tmp_path_factory):
    compiler = shutil.which('clang++')
    if not compiler:
        pytest.skip('Native compiler unavailable')
    root = Path(__file__).resolve().parents[2]
    target = tmp_path_factory.mktemp('park-record') / 'test.exe'
    build = subprocess.run([compiler, '-std=c++17',
                            str(root/'firmware/diagnostics/test_park_step_owner.cpp'),
                            '-o', str(target)], capture_output=True, text=True, timeout=30)
    assert build.returncode == 0, build.stderr
    run = subprocess.run([str(target), 'success'], capture_output=True, text=True, timeout=10)
    assert run.returncode == 0, run.stderr
    return bytes.fromhex(run.stdout.strip())


PLAN = {'schema': 'rocell.first_park_step_plan.v1',
        'source_goals': [2047, 2389, 1725, 2907, 1589, 2040, 2047],
        'target_goals': [2377, 1737]}


def test_decodes_and_assesses_native_record(raw):
    assert len(raw) == RECORD_BYTES == 1131
    record = decode_park_step_record(raw)
    assert record['target_goals'] == [2377, 1737]
    result = assess_park_step_record(raw, expected_boot='ab'*16, plan=PLAN)
    assert result['status'] == 'MEASURED_FIRST_STEP'
    assert result['actual_position_delta'] == [-12, 12]
    assert result['physical_rise_proven'] is False
    assert result['continuation_authorized'] is False


def test_rejects_changed_record(raw):
    with pytest.raises(ValueError):
        assess_park_step_record(raw, expected_boot='cd'*16, plan=PLAN)
    with pytest.raises(ValueError):
        assess_park_step_record(raw[:-1], expected_boot='ab'*16, plan=PLAN)
    changed = bytearray(raw)
    changed[10+16] = 0
    with pytest.raises(ValueError):
        assess_park_step_record(bytes(changed), expected_boot='ab'*16, plan=PLAN)
