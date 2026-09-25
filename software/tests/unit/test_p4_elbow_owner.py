from pathlib import Path
import shutil
import subprocess

import pytest

from rocell.application.large_pose_relief_record import assess_large_pose_relief_record
from rocell.application.large_pose_relief_host import LargePoseReliefHost
from rocell.application.wizard_diagnostic_export import verify_export

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope='module')
def executable(tmp_path_factory):
    compiler = shutil.which('clang++')
    if not compiler:
        pytest.skip('Native compiler unavailable')
    candidate = ROOT/'.firmware-tools/configured-diagnostic-candidate-r70/RoArm-M3_example'
    if not candidate.is_dir():
        pytest.fail('Stage the pinned r70 candidate before its native tests')
    target = tmp_path_factory.mktemp('p2-native')/'owner.exe'
    result = subprocess.run([compiler, '-std=c++17', '-I'+str(candidate),
        str(ROOT/'firmware/diagnostics/test_p4_elbow_owner.cpp'), '-o', str(target)],
        capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    return target


@pytest.mark.parametrize('mode', ['success', 'source_rejected', 'prewrite_changed',
    'wrong_goal', 'passive_drift', 'reverse', 'write_uncertain', 'evidence_failure'])
def test_exact_candidate(executable, mode):
    result = subprocess.run([str(executable), mode], capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr
    if mode == 'success':
        raw = bytes.fromhex(result.stdout.strip())
        assessment = assess_large_pose_relief_record(raw, expected_boot='ab'*16, profile='P4E')
        assert assessment['status'] == 'P4E_JOINT_ENDPOINT_MEASURED'
        assert assessment['position_delta_counts'] == [0,0,0,-66,0,0,0]
        assert assessment['synchronized_servo_ids'] == [14]
        with pytest.raises(ValueError, match='framing'):
            assess_large_pose_relief_record(raw, expected_boot='ab'*16)
        with pytest.raises(ValueError, match='Unknown reviewed'):
            assess_large_pose_relief_record(raw, expected_boot='ab'*16, profile='custom')


@pytest.mark.parametrize('wrong_domain', [False, True])
def test_host_export_and_receipt(executable, tmp_path, wrong_domain):
    run = subprocess.run([str(executable), 'success'], capture_output=True, text=True, check=True)
    raw = bytes.fromhex(run.stdout.strip())
    if wrong_domain:
        raw = b'RCRELIEF01'+raw[10:]
    calls = []
    def transport(method, path, body=b''):
        calls.append((method,path,body))
        return {'start':b'CAPTURING_START', 'status':b'AWAITING_DURABLE_EXPORT|1',
                'record':raw.hex().encode(), 'receipt':b'LARGE_POSE_P4E_RECORDED'}[path.rsplit('/',1)[1]]
    host = LargePoseReliefHost(transport, export_root=tmp_path, boot='ab'*16, profile='P4E')
    if wrong_domain:
        with pytest.raises(ValueError, match='framing'):
            host.run_once(pause=lambda _:None)
        assert not any(call[1].endswith('receipt') for call in calls)
    else:
        result = host.run_once(pause=lambda _:None)
        assert verify_export(Path(result['export']))['valid']
        assert result['assessment']['target_pose'] == 'P4E'
        assert calls[-1][1].endswith('receipt')
    assert calls[0][2] == b'P4E'
    with pytest.raises(ValueError):
        host.run_once()


def test_export_failure_never_receipts(executable, tmp_path, monkeypatch):
    from rocell.application import large_pose_relief_host as module
    run = subprocess.run([str(executable), 'success'], capture_output=True, text=True, check=True)
    calls=[]
    def transport(method,path,body=b''):
        calls.append(path)
        return {'start':b'CAPTURING_START','status':b'AWAITING_DURABLE_EXPORT|1',
                'record':run.stdout.strip().encode()}[path.rsplit('/',1)[1]]
    monkeypatch.setattr(module,'verify_export',lambda path: {'valid':False})
    host=LargePoseReliefHost(transport,export_root=tmp_path,boot='ab'*16,profile='P4E')
    with pytest.raises(ValueError,match='export verification failed'):
        host.run_once(pause=lambda _:None)
    assert not any(p.endswith('receipt') for p in calls)
    with pytest.raises(ValueError):host.run_once()
