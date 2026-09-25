import json
from pathlib import Path
import shutil
import subprocess

import pytest
from rocell.application.first_motion_contract import canonical


def test_actual_configured_challenge_route(tmp_path):
    compiler=shutil.which('clang++')
    if not compiler:pytest.skip('Host compiler required')
    root=Path(__file__).resolve().parents[2];exe=tmp_path/'routes.exe'
    build=subprocess.run([compiler,'-std=c++14','-Wall','-Wextra','-Werror',
        '-I'+str(root/'.firmware-tools/user/libraries/ArduinoJson/src'),
        str(root/'firmware/diagnostics/test_configured_diagnostic_routes.cpp'),'-o',str(exe)],
        capture_output=True,text=True,timeout=60)
    assert build.returncode==0,build.stderr
    doc=dict(schema='rocell.controller_diagnostics.v1',policy_id='inert-only',
        conversion_version='roarm-m3-example20260115-elbow-v1',start_port=8081,challenge_lifetime_us=10000,
        elbow_bounds=dict(minimum_rad=1.6,maximum_rad=1.9,maximum_speed=40,maximum_acceleration=1),
        whole_arm_policy=dict(joints=[[1900,2200]]*7,tracking_tolerance=2,
            maximum_pair_us=100,maximum_scan_us=1000,maximum_age_us=1000))
    path=tmp_path/'policy.json';path.write_bytes(canonical(doc))
    for mode in range(7):
        run=subprocess.run([str(exe),str(mode),str(path)],capture_output=True,text=True,timeout=10)
        assert run.returncode==0,(mode,run.stderr)
        result=json.loads(run.stdout)
        if mode==0:
            assert result==dict(schema='rocell.start_challenge.v1',boot_id='11'*16,nonce='22'*32,
                issued_us=1001,expires_us=11001)
        else:assert result=={'error':'DIAGNOSTICS_NOT_CONFIGURED'}
