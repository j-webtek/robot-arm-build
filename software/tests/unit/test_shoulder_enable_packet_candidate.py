from pathlib import Path
import shutil
import subprocess
import pytest


def test_actual_library_emits_only_pair_enable_packet(tmp_path):
    compiler=shutil.which('clang++')
    if not compiler:pytest.skip('Native compiler unavailable')
    root=Path(__file__).resolve().parents[2]
    library=root/'.firmware-tools/user/libraries/SCServo'
    source=root/'firmware/diagnostics/test_shoulder_enable_packet_candidate.cpp'
    executable=tmp_path/'shoulder-enable-wire.exe'
    built=subprocess.run([compiler,'-std=c++17','-I'+str(library),str(source),
        str(library/'SCS.cpp'),'-o',str(executable)],capture_output=True,text=True,timeout=30)
    assert built.returncode==0,built.stderr
    tested=subprocess.run([str(executable)],capture_output=True,text=True,timeout=10)
    assert tested.returncode==0,tested.stderr
    assert 'NO_HARDWARE; NO_ACK_PROOF' in tested.stdout
