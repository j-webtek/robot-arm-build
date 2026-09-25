from pathlib import Path
import shutil
import subprocess

import pytest

from rocell.application.park_reanchor_record import (
    assess_park_reanchor_record, export_park_reanchor_record,
    replay_park_reanchor_record,
)
from rocell.application.visible_shoulder_step_plan import (
    SOURCE_GOALS, SOURCE_POSITIONS, plan_visible_shoulder_step,
)


@pytest.fixture(scope='module')
def binary(tmp_path_factory):
    compiler = shutil.which('clang++')
    if not compiler:
        pytest.skip('Native compiler unavailable')
    root = Path(__file__).resolve().parents[2]
    target = tmp_path_factory.mktemp('visible-step-record') / 'test.exe'
    built = subprocess.run(
        [compiler, '-std=c++17', '-Wall', '-Wextra', '-Werror',
         str(root / 'firmware/diagnostics/test_park_reanchor_owner_r58.cpp'),
         '-o', str(target)], capture_output=True, text=True, timeout=30)
    assert built.returncode == 0, built.stderr
    return target


def raw(binary, mode='success'):
    result = subprocess.run([str(binary), mode], capture_output=True,
                            text=True, timeout=10)
    assert result.returncode == 0, result.stderr
    return bytes.fromhex(result.stdout.strip())


def plan():
    observation = {
        'category': 'STABLE_SAMPLED_POSE', 'origin': 'DEVICE_CAPTURE',
        'joints': [
            {'servo_id': 11 + index, 'last_goal': goal,
             'last_position': position, 'torque': 1,
             'controls_unchanged': True, 'position_span': 0}
            for index, (goal, position) in enumerate(zip(SOURCE_GOALS,
                                                         SOURCE_POSITIONS))
        ],
    }
    return plan_visible_shoulder_step(observation, observation_boot='11' * 16,
                                      observation_export_id='wizard-pose')


def test_visible_step_record_assesses_and_replays(binary, tmp_path):
    assessed = assess_park_reanchor_record(raw(binary), expected_boot='00' * 16,
                                            plan=plan())
    assert assessed['status'] == 'MEASURED_VISIBLE_STEP'
    assert assessed['actual_position_delta'] == [24, -24]
    assert assessed['endpoint_error_counts'] == [2, -1]
    saved = export_park_reanchor_record(tmp_path, raw(binary),
                                        expected_boot='00' * 16, plan=plan(),
                                        mode='visible-step-fixture')
    assert replay_park_reanchor_record(tmp_path, Path(saved).name,
                                       expected_boot='00' * 16,
                                       plan=plan()) == assessed


def test_visible_step_fault_is_not_success(binary):
    assessed = assess_park_reanchor_record(raw(binary, 'timeout'),
                                            expected_boot='00' * 16,
                                            plan=plan())
    assert assessed['status'] == 'FAULT_RECORDED'
    assert assessed['continuation_authorized'] is False
