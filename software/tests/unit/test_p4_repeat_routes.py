from pathlib import Path
import shutil
import subprocess
import pytest

ROOT=Path(__file__).resolve().parents[2]

def test_candidate_routes_twelve_legs(tmp_path):
    compiler=shutil.which('clang++')
    if not compiler:pytest.skip('Native compiler unavailable')
    binary=tmp_path/'routes.exe'
    staged=ROOT/'.firmware-tools/configured-diagnostic-candidate-r72/RoArm-M3_example'
    source=ROOT/'firmware/diagnostics/test_p4_repeat_routes.cpp'
    # Angle-include copy ensures the compiled header is the staged candidate.
    copied=tmp_path/'routes.cpp'
    copied.write_text(source.read_text().replace('#include "p4_repeat_routes.h"','#include <p4_repeat_routes.h>'))
    result=subprocess.run([compiler,'-std=c++17','-I'+str(staged),str(copied),'-o',str(binary)],capture_output=True,text=True,timeout=30)
    assert result.returncode==0,result.stderr
    subprocess.run([str(binary)],check=True,timeout=10)
