"""Native one-shot HTTP parser/listener with scripted network and servo bus."""
import json
import copy
from pathlib import Path
import shutil
import subprocess
import sys

import pytest
from test_supported_recovery_start import inputs
from rocell.application.supported_recovery_start import sign_recovery
from rocell.application.supported_recovery_review import assess_recovery, export_recovery, replay_recovery
from rocell.application.hold_transport_snapshot import collect_recovery_snapshot, collect_hold_snapshot
from rocell.application.hold_transport_snapshot import RECOVERY_STATUS as STATUS, RECOVERY_RECORD as RECORD
from rocell.application.hold_transport_snapshot import RecoveryHTTPReader
from rocell.application.hold_transport_export import (
    capture_recovery_transport, replay_recovery_transport_export, replay_recovery_transport_bundle,
    replay_hold_transport_bundle,
)
from rocell.application.product_ghost_export_review import _read


@pytest.mark.parametrize('path,budget', [('/rocell/diagnostics/status', 512),
    (RECORD+'12', 4608), (RECORD+'00', 4608), (STATUS, 513), (RECORD+'0', 4609)])
def test_recovery_reader_rejects_other_surface_and_latches(path, budget, monkeypatch):
    reader = RecoveryHTTPReader('127.0.0.1', 8080)
    def forbidden(*args, **kwargs): pytest.fail('Unexpected connection')
    monkeypatch.setattr(reader, '_get', forbidden)
    with pytest.raises(ValueError): reader(path, maximum_bytes=budget, timeout_seconds=3)
    with pytest.raises(ValueError): reader(STATUS, maximum_bytes=512, timeout_seconds=3)


def test_recovery_reader_preserves_exact_paths(monkeypatch):
    reader = RecoveryHTTPReader('127.0.0.1', 8080)
    calls = []
    def get(path, **budgets): calls.append((path, budgets));return b'{}'
    monkeypatch.setattr(reader, '_get', get)
    assert reader(STATUS, maximum_bytes=512, timeout_seconds=3) == b'{}'
    assert reader(RECORD+'7', maximum_bytes=4608, timeout_seconds=3) == b'{}'
    assert [c[0] for c in calls] == [STATUS, RECORD+'7']


def test_configured_recovery_listener_and_collection(tmp_path):
    compiler = shutil.which('clang++')
    if sys.platform != 'win32' or not compiler:
        pytest.skip('Windows crypto/compiler required')
    root = Path(__file__).resolve().parents[2]
    exe = tmp_path / 'recovery-listener.exe'
    built = subprocess.run([compiler, '-std=c++17',
        '-I'+str(root / '.firmware-tools/user/libraries/ArduinoJson/src'),
        str(root / 'firmware/diagnostics/test_configured_recovery_runtime.cpp'),
        '-lbcrypt', '-o', str(exe)], capture_output=True, text=True, timeout=60)
    assert built.returncode == 0, built.stderr
    policy, challenge, plan = inputs()
    token = tmp_path / 'test-token.bin'
    token.write_bytes(sign_recovery(plan, challenge, b'k'*32, approved_policy=policy))
    run = subprocess.run([str(exe), str(token)], capture_output=True, text=True, timeout=10)
    assert run.returncode == 0, run.stderr
    lines = [line.encode() for line in run.stdout.splitlines()]
    assert len(lines) == 9
    calls = []
    def get(path, **budgets):
        calls.append(path)
        assert budgets['timeout_seconds'] == 3.0
        return lines[0] if path == STATUS else lines[int(path.removeprefix(RECORD))+1]
    captured = collect_recovery_snapshot(get, expected_boot=challenge['boot_id'])
    assert captured['category'] == 'TRANSPORT_CAPTURED'
    assert calls == [STATUS]+[RECORD+str(i) for i in range(8)]+[STATUS]
    assert captured['endpoint_assessed'] is False
    kwargs = dict(expected_plan=json.loads(plan.encoded), expected_policy=policy, origin='SIMULATION')
    reviewed = assess_recovery(captured['records'], **kwargs)
    assert reviewed['category'] == 'SIMULATED_RECOVERY_VERIFIED'
    exported = export_recovery(tmp_path / 'exports', captured['records'], **kwargs)
    assert replay_recovery(exported['path']) == reviewed
    transport = capture_recovery_transport(tmp_path / 'transport', get, expected_boot=challenge['boot_id'])
    assert transport['replay_verified'] is True
    export_id = Path(transport['export_path']).name
    assert replay_recovery_transport_export(tmp_path / 'transport', export_id)['summary'] == transport['summary']
    bundle, _ = _read(tmp_path / 'transport', export_id, 'attachment-recovery-transport.json')
    with pytest.raises(ValueError): replay_hold_transport_bundle(bundle)
    for fault in ('path', 'hash', 'extra', 'summary'):
        bad = copy.deepcopy(bundle)
        if fault == 'path': bad['responses'][0]['path'] = '/rocell/diagnostics/status'
        if fault == 'hash': bad['responses'][0]['sha256'] = '0'*64
        if fault == 'extra': bad['responses'].append(bad['responses'][-1])
        if fault == 'summary': bad['summary']['category'] = 'FORGED'
        with pytest.raises(ValueError): replay_recovery_transport_bundle(bad)
    assert collect_hold_snapshot(lambda path, **kw: lines[0],
        expected_boot=challenge['boot_id'])['category'] == 'INCONCLUSIVE'
    for failed in range(10):
        attempts = []
        def interrupted(path, **budgets):
            attempts.append(path)
            if len(attempts)-1 == failed: raise OSError('Injected lost response')
            return get(path, **budgets)
        partial = collect_recovery_snapshot(interrupted, expected_boot=challenge['boot_id'])
        assert partial['category'] == 'INCONCLUSIVE'
        assert len(attempts) == failed+1
        assert len(partial['responses']) == failed
        attempts.clear()
        partial_export = capture_recovery_transport(tmp_path / 'partial', interrupted,
                                                    expected_boot=challenge['boot_id'])
        assert partial_export['replay_verified'] is True
        assert partial_export['summary']['category'] == 'INCONCLUSIVE'
        assert len(attempts) == failed+1
    calls.clear()
    def changed(path, **budgets):
        raw = get(path, **budgets)
        if len(calls) == 10:
            value = json.loads(raw);value['instance_id'] = '33'*16
            return json.dumps(value).encode()
        return raw
    assert collect_recovery_snapshot(changed, expected_boot=challenge['boot_id'])['category'] == 'INCONCLUSIVE'
