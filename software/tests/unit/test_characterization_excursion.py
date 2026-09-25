from pathlib import Path
import shutil
import subprocess
import pytest


def test_native_total_excursion(tmp_path):
    compiler=shutil.which('clang++')
    if not compiler:pytest.skip('Native compiler unavailable')
    source=Path(__file__).resolve().parents[2]/'firmware/diagnostics/test_characterization_excursion.cpp'
    binary=tmp_path/'excursion.exe'
    build=subprocess.run([compiler,'-std=c++17',str(source),'-lbcrypt','-o',str(binary)],capture_output=True,text=True,timeout=30)
    assert build.returncode==0,build.stderr
    for mode in ('outside','boundary','measured_outside'):
        run=subprocess.run([str(binary),mode],capture_output=True,text=True,timeout=10)
        assert run.returncode==0,(mode,run.stderr)
