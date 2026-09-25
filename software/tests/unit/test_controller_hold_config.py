import copy
import json
from pathlib import Path
import shutil
import subprocess
import pytest
from test_hold_prepared_start import fixture
from rocell.application.first_motion_contract import canonical


def test_native_strict_hold_configuration(tmp_path):
    compiler = shutil.which('clang++')
    if not compiler:
        pytest.skip('Native compiler required')
    root = Path(__file__).resolve().parents[2]
    exe = tmp_path / 'hold-config.exe'
    built = subprocess.run([compiler, '-std=c++17',
        '-I' + str(root / '.firmware-tools/user/libraries/ArduinoJson/src'),
        str(root / 'firmware/diagnostics/test_controller_hold_config.cpp'), '-o', str(exe)],
        capture_output=True, text=True, timeout=60)
    assert built.returncode == 0, built.stderr
    policy, _, _ = fixture()
    config = dict(schema='rocell.controller_hold.v1', command_id='reviewed-hold',
                  hold_policy=policy, start_port=8081)
    cases = [(canonical(config), True), (json.dumps(config).encode(), False),
             (canonical(config).replace(b'"start_port":8081', b'"start_port":8081.0'), False),
             (canonical(config).replace(b'"command_id":', b'"command_id":"x","command_id":'), False)]
    for edit in (
        lambda c: c.update(extra=1), lambda c: c.update(start_port=80),
        lambda c: c.update(command_id='bad/name'),
        lambda c: c['hold_policy'].update(speed=0),
        lambda c: c['hold_policy'].update(permit_explicit_enable=True),
        lambda c: c['hold_policy'].update(servo_id=12),
        lambda c: c['hold_policy'].update(baseline_gap_us=600000),
        lambda c: c['hold_policy'].update(joints=[[0,4096]]*7),
        lambda c: c['hold_policy'].pop('drift'),
    ):
        altered = copy.deepcopy(config);edit(altered);cases.append((canonical(altered), False))
    for i, (payload, valid) in enumerate(cases):
        path = tmp_path / f'config-{i}.json';path.write_bytes(payload)
        result = subprocess.run([str(exe), str(path), str(int(valid))], capture_output=True, text=True, timeout=10)
        assert result.returncode == 0, result.stderr
