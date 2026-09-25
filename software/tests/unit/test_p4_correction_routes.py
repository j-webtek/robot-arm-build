from pathlib import Path
import shutil
import subprocess
import pytest

ROOT=Path(__file__).resolve().parents[2]


def test_candidate_routes_sixteen_legs(tmp_path):
    compiler=shutil.which('clang++')
    if not compiler:pytest.skip('Native compiler unavailable')
    binary=tmp_path/'routes.exe'
    source=ROOT/'firmware/diagnostics/test_p4_correction_routes.cpp'
    result=subprocess.run([compiler,'-std=c++17','-I'+str(ROOT/'firmware/diagnostics'),
        '-I'+str(ROOT/'.firmware-tools/configured-diagnostic-candidate-r72/RoArm-M3_example'),
        str(source),'-o',str(binary)],capture_output=True,text=True,timeout=30)
    assert result.returncode==0,result.stderr
    subprocess.run([str(binary)],check=True,timeout=10)


def test_staged_candidate_uses_reviewed_route(tmp_path):
    compiler=shutil.which('clang++')
    if not compiler:pytest.skip('Native compiler unavailable')
    staged=ROOT/'.firmware-tools/configured-diagnostic-candidate-r73/RoArm-M3_example'
    binary=tmp_path/'staged-routes.exe'
    source=ROOT/'firmware/diagnostics/test_p4_correction_routes.cpp'
    copied=tmp_path/'staged-routes.cpp'
    copied.write_text(source.read_text().replace('#include "p4_correction_routes.h"',
        '#include <p4_correction_routes.h>'))
    result=subprocess.run([compiler,'-std=c++17','-I'+str(staged),
        str(copied),'-o',str(binary)],capture_output=True,text=True,timeout=30)
    assert result.returncode==0,result.stderr
    subprocess.run([str(binary)],check=True,timeout=10)
