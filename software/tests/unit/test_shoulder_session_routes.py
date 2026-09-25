from pathlib import Path
import shutil
import subprocess
import pytest


@pytest.mark.parametrize('settling',[False,True])
def test_routes_never_dispatch_servo_operations(tmp_path,settling):
    compiler=shutil.which('clang++')
    if not compiler:pytest.skip('Native compiler unavailable')
    root=Path(__file__).resolve().parents[2];binary=tmp_path/'routes.exe'
    built=subprocess.run([compiler,'-std=c++17',
        '-I'+str(root/'.firmware-tools/user/libraries/ArduinoJson/src'),
        str(root/'firmware/diagnostics'/('test_shoulder_fault_settling_routes.cpp' if settling else 'test_shoulder_session_routes.cpp')),'-o',str(binary)],
        capture_output=True,text=True,timeout=30)
    assert built.returncode==0,built.stderr
    result=subprocess.run([str(binary)],capture_output=True,text=True,timeout=10)
    assert result.returncode==0,result.stderr
    assert ('SETTLING_ROUTES_PASSED' if settling else 'SHOULDER_ROUTES_OFFLINE_PASSED') in result.stdout
