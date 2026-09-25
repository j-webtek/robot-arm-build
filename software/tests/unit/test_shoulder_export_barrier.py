from pathlib import Path
import shutil
import subprocess
import pytest


def test_receipt_required_before_release(tmp_path):
    compiler=shutil.which('clang++')
    if not compiler:pytest.skip('Native compiler unavailable')
    source=Path(__file__).resolve().parents[2]/'firmware/diagnostics/test_shoulder_export_barrier.cpp'
    binary=tmp_path/'barrier.exe'
    built=subprocess.run([compiler,'-std=c++17',str(source),'-o',str(binary)],capture_output=True,text=True,timeout=30)
    assert built.returncode==0,built.stderr
    result=subprocess.run([str(binary)],capture_output=True,text=True,timeout=10)
    assert result.returncode==0,result.stderr
    assert 'SHOULDER_EXPORT_BARRIER_OFFLINE_PASSED' in result.stdout
