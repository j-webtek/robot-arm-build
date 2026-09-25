from pathlib import Path
import shutil
import subprocess

import pytest

from rocell.application.park_reanchor_host import ParkReanchorHost
from rocell.application.park_reanchor_plan import OFFSET_GOALS


@pytest.fixture(scope='module')
def binary(tmp_path_factory):
    compiler = shutil.which('clang++')
    if not compiler:
        pytest.skip('Native compiler unavailable')
    root = Path(__file__).resolve().parents[2]
    target = tmp_path_factory.mktemp('park-return-host') / 'test.exe'
    built = subprocess.run(
        [compiler, '-std=c++17', '-Wall', '-Wextra', '-Werror',
         str(root / 'firmware/diagnostics/test_park_reanchor_owner.cpp'),
         '-o', str(target)], capture_output=True, text=True, timeout=30,
    )
    assert built.returncode == 0, built.stderr
    return target


def record(binary, mode):
    ran = subprocess.run([str(binary), mode], capture_output=True, text=True,
                         timeout=10)
    assert ran.returncode == 0, ran.stderr
    return bytes.fromhex(ran.stdout.strip())


def plan():
    return {
        'schema': 'rocell.park_reanchor_plan.v1',
        'target_goals': [2389, 1725], 'source_goals': list(OFFSET_GOALS),
        'observation_boot': '11'*16, 'movement_authorized': False,
        'physical_clearance_verified': False,
    }


class Transport:
    def __init__(self, raw, status):
        self.raw = raw
        self.status = status
        self.calls = []
        self.status_reads = 0

    def __call__(self, method, path, body=None):
        self.calls.append((method, path, body))
        if path.endswith('/start'):
            return b'CAPTURING_START'
        if path.endswith('/status'):
            self.status_reads += 1
            if self.status_reads == 1:
                return b'NEW|0'
            return self.status
        if path.endswith('/record'):
            return self.raw.hex().encode('ascii')
        if path.endswith('/receipt'):
            return b'RETURN_RECORDED'
        raise AssertionError(path)


def test_success_exports_before_receipt_and_cannot_repeat(binary, tmp_path):
    transport = Transport(record(binary, 'success'), b'AWAITING_DURABLE_EXPORT|1')
    host = ParkReanchorHost(transport, export_root=tmp_path, boot='00'*16,
                            plan=plan())
    result = host.run_once()
    assert result['assessment']['status'] == 'MEASURED_RETURN'
    assert Path(result['export']).is_dir()
    assert transport.calls[-1][1].endswith('/receipt')
    with pytest.raises(ValueError, match='One bounded'):
        host.run_once()
    assert sum(path.endswith('/start') for _, path, _ in transport.calls) == 1
    assert transport.calls[0][0:2] == ('GET', '/rocell/park-return/status')


def test_fault_exports_without_receipt_or_retry(binary, tmp_path):
    transport = Transport(record(binary, 'timeout'), b'ENDPOINT_TIMEOUT|1')
    host = ParkReanchorHost(transport, export_root=tmp_path, boot='00'*16,
                            plan=plan())
    with pytest.raises(ValueError, match='fault exported'):
        host.run_once()
    assert not any(path.endswith('/receipt') for _, path, _ in transport.calls)
    assert len(list(tmp_path.glob('wizard-*'))) == 2
    with pytest.raises(ValueError, match='One bounded'):
        host.run_once()


def test_rejects_same_boot_observation_and_claims_one_use():
    invalid = plan()
    invalid['observation_boot'] = '00'*16
    with pytest.raises(ValueError, match='Reviewed inert'):
        ParkReanchorHost(lambda *args: None, export_root='.', boot='00'*16,
                         plan=invalid)


def test_nonidle_signed_status_stops_before_start(tmp_path):
    class Nonidle:
        def __init__(self):
            self.calls = []

        def __call__(self, method, path, body=None):
            self.calls.append((method, path))
            return b'FAULT|0'

    transport = Nonidle()
    host = ParkReanchorHost(transport, export_root=tmp_path, boot='00'*16,
                            plan=plan())
    with pytest.raises(ValueError, match='not idle'):
        host.run_once()
    assert transport.calls == [('GET', '/rocell/park-return/status')]
    with pytest.raises(ValueError, match='One bounded'):
        host.run_once()
