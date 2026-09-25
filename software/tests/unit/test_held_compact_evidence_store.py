"""Exact byte comparison against the full store on synthetic native captures."""
from pathlib import Path
import shutil
import subprocess
import sys
import pytest


def test_compact_store(tmp_path):
    compiler=shutil.which('clang++')
    if sys.platform!='win32' or not compiler:
        pytest.skip('Windows native crypto/compiler required')
    root=Path(__file__).resolve().parents[2];exe=tmp_path/'compact.exe'
    build=subprocess.run([compiler,'-std=c++17',
        '-I'+str(root/'.firmware-tools/user/libraries/ArduinoJson/src'),
        str(root/'firmware/diagnostics/test_held_compact_evidence_store.cpp'),
        '-lbcrypt','-o',str(exe)],capture_output=True,text=True,timeout=60)
    assert build.returncode==0,build.stderr
    run=subprocess.run([str(exe)],capture_output=True,text=True,timeout=20)
    assert run.returncode==0,run.stderr
