from pathlib import Path
import shutil
import subprocess
import sys
import json
import pytest
from test_hold_prepared_start import fixture
from rocell.application.hold_command_contract import sign_hold
from rocell.application.hold_transport_snapshot import collect_hold_snapshot
from rocell.application.servo_transport_snapshot import STATUS, RECORD
from rocell.application.hold_transport_export import capture_hold_transport, replay_hold_transport_export


@pytest.mark.parametrize('source', ['test_allocated_hold_runtime.cpp', 'test_hold_listener.cpp',
                                   'test_configured_hold_runtime.cpp'])
def test_checked_native_runtime_allocation(tmp_path, source):
    compiler = shutil.which('clang++')
    if sys.platform != 'win32' or not compiler:
        pytest.skip('Windows native crypto/compiler required')
    root = Path(__file__).resolve().parents[2]
    exe = tmp_path / 'allocated-hold.exe'
    built = subprocess.run([compiler, '-std=c++17',
        '-I' + str(root / '.firmware-tools/user/libraries/ArduinoJson/src'),
        str(root / 'firmware/diagnostics' / source), '-lbcrypt', '-o', str(exe)],
        capture_output=True, text=True, timeout=60)
    assert built.returncode == 0, built.stderr
    policy, plan, challenge = fixture()
    token = tmp_path / 'test-token.bin'
    token.write_bytes(sign_hold(plan, challenge, b'k'*32, approved_policy=policy))
    result = subprocess.run([str(exe), str(token)], capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr
    if source == 'test_configured_hold_runtime.cpp':
        lines = [line.encode() for line in result.stdout.splitlines()]
        assert len(lines) == 9
        calls = []
        def get(path, **budgets):
            calls.append(path)
            assert budgets['timeout_seconds'] == 3.0
            return lines[0] if path == STATUS else lines[int(path.removeprefix(RECORD))+1]
        captured = collect_hold_snapshot(get, expected_boot='11'*16)
        assert captured['category'] == 'TRANSPORT_CAPTURED' and len(captured['records']) == 8
        assert calls == [STATUS] + [RECORD+str(i) for i in range(8)] + [STATUS]
        assert captured['endpoint_assessed'] is False
        exported = capture_hold_transport(tmp_path / 'transport-exports', get, expected_boot='11'*16)
        assert replay_hold_transport_export(tmp_path / 'transport-exports',
            Path(exported['export_path']).name)['summary']['category'] == 'TRANSPORT_CAPTURED'
        for fail_index in range(10):
            attempts = []
            def interrupted(path, **budgets):
                attempts.append(path)
                if len(attempts)-1 == fail_index:
                    raise OSError('simulated lost response')
                return get(path, **budgets)
            partial = collect_hold_snapshot(interrupted, expected_boot='11'*16)
            assert partial['category'] == 'INCONCLUSIVE'
            assert len(attempts) == fail_index+1
            assert len(partial['responses']) == fail_index
            attempts.clear()
            exported = capture_hold_transport(tmp_path / 'transport-exports', interrupted, expected_boot='11'*16)
            assert exported['replay_verified'] and exported['summary']['category'] == 'INCONCLUSIVE'
            assert len(attempts) == fail_index+1
        attempts = []
        def changed(path, **budgets):
            attempts.append(path)
            data = get(path, **budgets)
            if len(attempts) == 10:
                value = json.loads(data);value['instance_id'] = '33'*16
                return json.dumps(value).encode()
            return data
        assert collect_hold_snapshot(changed, expected_boot='11'*16)['category'] == 'INCONCLUSIVE'
