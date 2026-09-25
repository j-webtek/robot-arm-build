import hashlib
from pathlib import Path
import shutil
import subprocess

import pytest

from rocell.application.fixed_pair_reanchor_host import FixedPairReanchorHost


PLAN = {'schema': 'rocell.fixed_pair_reanchor_plan.v1',
        'target_goals': [2389, 1725], 'expected_positions': [2391, 1724]}


@pytest.fixture(scope='module')
def raw(tmp_path_factory):
    compiler = shutil.which('clang++')
    if not compiler:
        pytest.skip('Native compiler unavailable')
    root = Path(__file__).resolve().parents[2]
    source = root / 'firmware/diagnostics/test_fixed_pair_reanchor_owner.cpp'
    target = tmp_path_factory.mktemp('reanchor-host') / 'owner.exe'
    build = subprocess.run([compiler, '-std=c++17', str(source), '-o', str(target)],
                           capture_output=True, text=True, timeout=30)
    assert build.returncode == 0, build.stderr
    run = subprocess.run([str(target), 'success'], capture_output=True, text=True, timeout=10)
    assert run.returncode == 0, run.stderr
    return bytes.fromhex(run.stdout.strip())


def test_host_exports_before_receipt_and_never_retries(tmp_path, raw):
    calls = []

    def transport(method, path, body=b''):
        calls.append((method, path, body))
        return {
            '/rocell/reanchor/start': b'CAPTURING_START',
            '/rocell/reanchor/status': b'AWAITING_DURABLE_EXPORT|1',
            '/rocell/reanchor/record': raw.hex().encode('ascii'),
            '/rocell/reanchor/receipt': b'REANCHOR_VERIFIED',
        }[path]

    owner = FixedPairReanchorHost(transport, export_root=tmp_path,
                                  boot='ab'*16, plan=PLAN)
    result = owner.run_once(pause=lambda _: None)
    assert Path(result['export']).is_dir()
    assert result['assessment']['result']['status'] == 'GOAL_AND_ENDPOINT_VERIFIED'
    assert calls[-1] == ('POST', '/rocell/reanchor/receipt',
                         hashlib.sha256(raw).hexdigest().encode('ascii'))
    assert result['physical_motion_proven'] is False
    with pytest.raises(ValueError):
        owner.run_once()


def test_host_bad_record_stops_before_receipt(tmp_path, raw):
    calls = []

    def transport(method, path, body=b''):
        calls.append(path)
        return {
            '/rocell/reanchor/start': b'CAPTURING_START',
            '/rocell/reanchor/status': b'AWAITING_DURABLE_EXPORT|1',
            '/rocell/reanchor/record': raw.hex().encode('ascii'),
        }[path]

    owner = FixedPairReanchorHost(transport, export_root=tmp_path,
                                  boot='cd'*16, plan=PLAN)
    with pytest.raises(ValueError, match='boot mismatch'):
        owner.run_once(pause=lambda _: None)
    assert '/rocell/reanchor/receipt' not in calls
    assert not list(tmp_path.glob('wizard-*'))
