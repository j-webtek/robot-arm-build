"""Build pinned real servo library with a host-only serial emulator."""
import hashlib
from pathlib import Path
import shutil
import subprocess
import pytest


@pytest.mark.parametrize('source', ['test_hold_servo_wire.cpp', 'test_held_leg_servo_wire.cpp', 'test_shoulder_rise_wire.cpp'])
def test_hold_owner_actual_library_wire_bytes(tmp_path, source):
    compiler = shutil.which('clang++')
    if not compiler:
        pytest.skip('Host compiler required')
    root = Path(__file__).resolve().parents[2]
    library = root / '.firmware-tools/user/libraries/SCServo'
    hashes = {
        'SCS.cpp': '3428d9bafceec76121d7cbdb5acc37a31b6f9babc74957dfa54d26e30ea0ed3d',
        'SCSerial.cpp': '8869cf77b092479cbbe755d29621abcc181142d57b191a54632a6ba3950c5bb3',
        'SMS_STS.cpp': '9de0ce38764d38dd65b98638c8d660ae3a375e74bb08e536228b414e159e9d58',
        'INST.h': 'af9cb2d237f64093caf19694807f88ab2f343f6e8dcb3ec1c7faaffc43cedbb9',
        'SCS.h': 'a1a54a1568ff01183cf84ccc3468061cf9a13e53f2707ceac6e1f8c1f3407227',
        'SCSerial.h': '6b5270d0a9fe8603b193880bcd6a665f77b24bc54d884298f8db9fd8d7e96484',
        'SMS_STS.h': 'efa947e4609dbcd9810c9e907f4a414d335f6647e931bae85466879667e78406',
    }
    for name, expected in hashes.items():
        assert hashlib.sha256((library / name).read_bytes()).hexdigest() == expected
    diagnostics = root / 'firmware/diagnostics'
    exe = tmp_path / 'hold-wire.exe'
    result = subprocess.run([
        compiler, '-std=c++14', '-DARDUINO=100',
        '-I', str(diagnostics / 'servo_wire_test_stubs'), '-I', str(library),
        str(diagnostics / source),
        *(str(library / name) for name in hashes if name.endswith('.cpp')), '-o', str(exe),
    ], capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stderr
    result = subprocess.run([str(exe)], capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr
