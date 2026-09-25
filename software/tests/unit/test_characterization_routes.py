import shutil
import subprocess
from pathlib import Path
import pytest


def test_route_binding_offline(tmp_path):
    compiler=shutil.which('clang++')
    if not compiler:pytest.skip('Native compiler unavailable')
    root=Path(__file__).resolve().parents[2]
    binary=tmp_path/'routes.exe'
    build=subprocess.run([compiler,'-std=c++17',str(root/'firmware/diagnostics/test_characterization_routes.cpp'),
                          '-o',str(binary)],capture_output=True,text=True,timeout=30)
    assert build.returncode==0,build.stderr
    run=subprocess.run([str(binary)],capture_output=True,text=True,timeout=10)
    assert run.returncode==0,run.stderr
