import shutil
import subprocess
from pathlib import Path
import pytest


def test_bounded_evidence_lifecycle(tmp_path):
    compiler=shutil.which('clang++')
    if not compiler:pytest.skip('Native compiler unavailable')
    source=Path(__file__).resolve().parents[2]/'firmware/diagnostics/test_characterization_evidence.cpp'
    binary=tmp_path/'evidence.exe'
    build=subprocess.run([compiler,'-std=c++17',str(source),'-o',str(binary)],capture_output=True,text=True,timeout=30)
    assert build.returncode==0,build.stderr
    run=subprocess.run([str(binary)],capture_output=True,text=True,timeout=10)
    assert run.returncode==0,run.stderr
