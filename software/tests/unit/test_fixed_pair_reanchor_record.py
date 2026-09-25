from pathlib import Path
import shutil
import subprocess

import pytest

from rocell.application.fixed_pair_reanchor_record import (
    RECORD_BYTES, assess_fixed_pair_reanchor_record,
    decode_fixed_pair_reanchor_record, export_fixed_pair_reanchor_fixture,
    replay_fixed_pair_reanchor_fixture,
)


@pytest.fixture(scope='module')
def raw(tmp_path_factory):
    compiler = shutil.which('clang++')
    if not compiler:
        pytest.skip('Native compiler unavailable')
    root = Path(__file__).resolve().parents[2]
    target = tmp_path_factory.mktemp('fixed-reanchor-wire') / 'test.exe'
    build = subprocess.run([compiler, '-std=c++17',
                            str(root/'firmware/diagnostics/test_fixed_pair_reanchor_owner.cpp'),
                            '-o', str(target)], capture_output=True, text=True, timeout=30)
    assert build.returncode == 0, build.stderr
    run = subprocess.run([str(target), 'success'], capture_output=True, text=True, timeout=10)
    assert run.returncode == 0, run.stderr
    return bytes.fromhex(run.stdout.strip())


PLAN = {'schema': 'rocell.fixed_pair_reanchor_plan.v1',
        'target_goals': [2389, 1725], 'expected_positions': [2391, 1724]}


def test_native_record_decodes_and_assesses(raw):
    assert len(raw) == RECORD_BYTES
    record = decode_fixed_pair_reanchor_record(raw)
    assert record['boot'] == 'ab'*16
    assert record['writes_attempted'] == 1
    assert [record['start'][-1]['joints'][i]['goal'] for i in (1, 2)] == [2386, 1728]
    result = assess_fixed_pair_reanchor_record(raw, expected_boot='ab'*16, plan=PLAN)
    assert result['result']['status'] == 'GOAL_AND_ENDPOINT_VERIFIED'
    assert result['result']['position_delta'] == [1, -1]
    assert result['movement_authorized'] is False


def test_native_record_durable_fixture_replays(tmp_path, raw):
    saved = export_fixed_pair_reanchor_fixture(tmp_path, raw,
        expected_boot='ab'*16, plan=PLAN)
    replay = replay_fixed_pair_reanchor_fixture(tmp_path, Path(saved).name,
        expected_boot='ab'*16, plan=PLAN)
    assert replay['result']['status'] == 'GOAL_AND_ENDPOINT_VERIFIED'


@pytest.mark.parametrize('offset,value', [
    (0, 0),                # Domain
    (10, 0),               # Boot identity
    (34, 0),               # Write count
    (35+16+20+2, 0),      # High byte of servo 12's start goal
])
def test_native_record_tampering_rejected(raw, offset, value):
    damaged = bytearray(raw); damaged[offset] = value
    with pytest.raises(ValueError):
        assess_fixed_pair_reanchor_record(bytes(damaged), expected_boot='ab'*16, plan=PLAN)
