"""Offline new-profile and unchanged legacy-profile regression execution."""
from pathlib import Path
import shutil
import subprocess
import pytest


@pytest.mark.parametrize('name',['test_six_count_recovery.cpp','test_supported_recovery.cpp'])
def test_six_count_profile_and_legacy_regressions(tmp_path,name):
    compiler=shutil.which('clang++')
    if not compiler:pytest.skip('Native compiler required')
    source=Path(__file__).resolve().parents[2]/'firmware/diagnostics'/name
    executable=tmp_path/'six-count.exe'
    subprocess.run([compiler,'-std=c++17',str(source),'-o',str(executable)],
                   capture_output=True,check=True,timeout=60)
    subprocess.run([str(executable)],capture_output=True,check=True,timeout=10)
