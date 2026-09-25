import hashlib
from pathlib import Path
import shutil
import subprocess

import pytest

from rocell.application.park_step_host import ParkStepHost


PLAN = {'schema': 'rocell.first_park_step_plan.v1',
        'source_goals': [2047, 2389, 1725, 2907, 1589, 2040, 2047],
        'target_goals': [2377, 1737], 'movement_authorized': False,
        'observation_boot': 'cd'*16, 'physical_clearance_verified': False}


@pytest.fixture(scope='module')
def raw(tmp_path_factory):
    compiler = shutil.which('clang++')
    if not compiler:
        pytest.skip('Native compiler unavailable')
    root = Path(__file__).resolve().parents[2]
    target = tmp_path_factory.mktemp('park-host') / 'owner.exe'
    build = subprocess.run([compiler, '-std=c++17',
                            str(root/'firmware/diagnostics/test_park_step_owner.cpp'),
                            '-o', str(target)], capture_output=True, text=True, timeout=30)
    assert build.returncode == 0, build.stderr
    run = subprocess.run([str(target), 'success'], capture_output=True, text=True, timeout=10)
    assert run.returncode == 0, run.stderr
    return bytes.fromhex(run.stdout.strip())


def test_exports_replays_and_receipts_once(tmp_path, raw):
    calls = []

    def transport(method, path, body=b''):
        calls.append((method, path, body))
        return {
            '/rocell/park-step/start': b'CAPTURING_START',
            '/rocell/park-step/status': b'AWAITING_DURABLE_EXPORT|1',
            '/rocell/park-step/record': raw.hex().encode('ascii'),
            '/rocell/park-step/receipt': b'PARK_STEP_RECORDED',
        }[path]

    host = ParkStepHost(transport, export_root=tmp_path, boot='ab'*16, plan=PLAN)
    result = host.run_once(pause=lambda _: None)
    assert Path(result['export']).is_dir()
    assert result['assessment']['status'] == 'MEASURED_FIRST_STEP'
    assert calls[0] == ('POST', '/rocell/park-step/start', b'2377,1737')
    assert calls[-1] == ('POST', '/rocell/park-step/receipt',
                         hashlib.sha256(raw).hexdigest().encode('ascii'))
    assert result['physical_rise_proven'] is False
    with pytest.raises(ValueError):
        host.run_once()


def test_invalid_record_never_receipts(tmp_path, raw):
    calls = []

    def transport(method, path, body=b''):
        calls.append(path)
        return {
            '/rocell/park-step/start': b'CAPTURING_START',
            '/rocell/park-step/status': b'AWAITING_DURABLE_EXPORT|1',
            '/rocell/park-step/record': raw.hex().encode('ascii'),
        }[path]

    host = ParkStepHost(transport, export_root=tmp_path, boot='ef'*16, plan=PLAN)
    with pytest.raises(ValueError, match='identity mismatch'):
        host.run_once(pause=lambda _: None)
    assert '/rocell/park-step/receipt' not in calls
    assert not list(tmp_path.glob('wizard-*'))


def test_rejects_same_boot_pose_checkpoint(tmp_path):
    with pytest.raises(ValueError, match='Reviewed inert first-step plan required'):
        ParkStepHost(lambda *_: None, export_root=tmp_path, boot='ab'*16,
                     plan=dict(PLAN, observation_boot='ab'*16))


def test_terminal_fault_is_exported_without_retry_or_receipt(tmp_path):
    calls = []

    def transport(method, path, body=b''):
        calls.append((method, path))
        return b'CAPTURING_START' if path.endswith('/start') else b'ENDPOINT_GATE_FAILED|1'

    host = ParkStepHost(transport, export_root=tmp_path, boot='ab'*16, plan=PLAN)
    with pytest.raises(ValueError, match='terminal fault exported'):
        host.run_once(pause=lambda _: None)
    assert calls == [('POST', '/rocell/park-step/start'),
                     ('GET', '/rocell/park-step/status')]
    from rocell.application.wizard_diagnostic_export import verify_export
    folders = list(tmp_path.glob('wizard-*'))
    assert len(folders) == 1 and verify_export(folders[0])['valid']
    assert (folders[0] / 'attachment-park-step-terminal-status.txt').read_bytes() == b'ENDPOINT_GATE_FAILED|1'


def test_timeout_retains_raw_fault_record_without_receipt(tmp_path, raw):
    calls = []

    def transport(method, path, body=b''):
        calls.append((method, path))
        if path.endswith('/start'):
            return b'CAPTURING_START'
        if path.endswith('/status'):
            return b'ENDPOINT_TIMEOUT|1'
        if path.endswith('/record'):
            return raw.hex().encode('ascii')
        raise AssertionError('No receipt is allowed for a fault')

    host = ParkStepHost(transport, export_root=tmp_path, boot='ab'*16, plan=PLAN)
    with pytest.raises(ValueError, match='terminal fault exported'):
        host.run_once(pause=lambda _: None)
    assert calls == [('POST', '/rocell/park-step/start'),
                     ('GET', '/rocell/park-step/status'),
                     ('GET', '/rocell/park-step/record')]
    folders = list(tmp_path.glob('wizard-*'))
    assert len(folders) == 1
    assert (folders[0] / 'attachment-park-step-fault.hex.txt').read_bytes() == raw.hex().encode()
