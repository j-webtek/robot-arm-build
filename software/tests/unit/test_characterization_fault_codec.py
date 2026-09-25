import subprocess
from pathlib import Path
import pytest
from test_shoulder_characterization_owner import native
from rocell.application.characterization_fault_codec import decode_fault, export_fault


@pytest.mark.parametrize('mode,reason,writes', [
    ('read_failure', 'FEEDBACK_OR_BOUNDS', 4),
    ('neighbor', 'NEIGHBOR_CHANGED', 4),
    ('receipt_replay', 'EXPORT_RECEIPT_REJECTED', 4),
    ('export_interrupted', 'EXPORT_DEADLINE', 4),
    ('cancel', 'ADMISSION_LOST', 3),
])
def test_native_fault_export(native, tmp_path, mode, reason, writes):
    path = tmp_path/'capture'
    run = subprocess.run([str(native), mode, str(path)], capture_output=True, text=True, timeout=10)
    assert run.returncode == 0, run.stderr
    raw = Path(str(path)+'.fault').read_bytes()
    decoded = decode_fault(raw)
    assert decoded['reason'] == reason and decoded['writes_attempted'] == writes
    assert decoded['last_valid_pose'] is not None
    assert not decoded['pose_is_current'] and not decoded['movement_authorized']
    exported = export_fault(tmp_path/'exports', raw)
    assert exported['reason'] == reason
    for bad in (raw[:-1], raw+b'\0', b'X'+raw[1:]):
        with pytest.raises(ValueError):
            decode_fault(bad)


def test_fault_without_valid_pose():
    reason = b'ADMISSION_LOST'
    raw = b'RCCFAULT01\0'+bytes([len(reason)])+reason+bytes([1, 0, 0])+bytes(8)+b'\0'
    assert decode_fault(raw)['last_valid_pose'] is None
