import subprocess
import pytest
from test_shoulder_characterization_owner import native
from rocell.application.characterization_result_codec import decode_result, export_result


@pytest.fixture
def artifact(native, tmp_path):
    path = tmp_path / 'native-result.bin'
    run = subprocess.run([str(native), 'miss', str(path)], capture_output=True,
                         text=True, timeout=10)
    assert run.returncode == 0, run.stderr
    return path.read_bytes()


def test_decode_real_native_artifact(artifact):
    result = decode_result(artifact)
    assert result['leg'] == 0 and result['legs'] == 12
    assert result['outcome'] == 'SETTLED_MISS'
    final = result['observations'][-1]['joints']
    assert [final[i]['position']-final[i]['goal'] for i in (1, 2)] == [9, -7]
    assert result['physical_accuracy_verified'] is False


def test_verified_readable_export(artifact, tmp_path):
    result = export_result(tmp_path / 'exports', artifact)
    assert result['outcome'] == 'SETTLED_MISS'
    assert not result['movement_authorized'] and not result['receipt_issued']


def test_failed_export_rejected(artifact, tmp_path, monkeypatch):
    from rocell.application import wizard_diagnostic_export
    monkeypatch.setattr(wizard_diagnostic_export, 'verify_export', lambda _: {'valid': False})
    with pytest.raises(ValueError, match='verification'):
        export_result(tmp_path / 'exports', artifact)


@pytest.mark.parametrize('mutation', ['magic', 'truncated', 'trailing', 'legs', 'budget', 'feedback'])
def test_reject_malformed_result(artifact, mutation):
    data = bytearray(artifact)
    if mutation == 'magic': data[0] ^= 1
    elif mutation == 'truncated': data = data[:-1]
    elif mutation == 'trailing': data += b'\0'
    elif mutation == 'legs': data[12] = 255
    elif mutation == 'budget': data[13:21] = b'\xff'*8
    elif mutation == 'feedback': data[-15] ^= 1
    with pytest.raises(ValueError):
        decode_result(bytes(data))
