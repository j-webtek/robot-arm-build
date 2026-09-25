import json
from pathlib import Path
import shutil
import subprocess
import pytest


def test_generated_motion_route_respects_shared_claim(tmp_path):
    compiler=shutil.which('clang++')
    if not compiler:pytest.skip('Host compiler required')
    root=Path(__file__).resolve().parents[2]
    executable=tmp_path/'composition.exe'
    build=subprocess.run([compiler,'-std=c++14','-Wall','-Wextra','-Werror',
        '-DROCELL_TEST_BASELINE_COMPOSITION',
        '-I'+str(root/'.firmware-tools/user/libraries/ArduinoJson/src'),
        str(root/'firmware/diagnostics/test_configured_diagnostic_routes.cpp'),
        '-o',str(executable)],capture_output=True,text=True,timeout=60)
    assert build.returncode==0,build.stderr
    from rocell.application.first_motion_contract import canonical
    doc=dict(schema='rocell.controller_diagnostics.v1',policy_id='inert-only',
        conversion_version='roarm-m3-example20260115-elbow-v1',start_port=8081,
        challenge_lifetime_us=10000,
        elbow_bounds=dict(minimum_rad=1.6,maximum_rad=1.9,maximum_speed=40,maximum_acceleration=1),
        whole_arm_policy=dict(joints=[[1900,2200]]*7,tracking_tolerance=2,
            maximum_pair_us=100,maximum_scan_us=1000,maximum_age_us=1000))
    path=tmp_path/'policy.json';path.write_bytes(canonical(doc))
    for mode in (0,1,6,8):
        result=subprocess.run([str(executable),str(mode),str(path)],
                              capture_output=True,text=True,timeout=10)
        assert result.returncode==0,(mode,result.stderr)


def test_candidate_wiring_and_old_candidate_preserved():
    root=Path(__file__).resolve().parents[2]/'.firmware-tools'
    old=root/'configured-diagnostic-candidate-r2/RoArm-M3_example'
    new=root/'configured-diagnostic-candidate-r3/RoArm-M3_example'
    assert 'rocellSessionClaim' not in (old/'configured_native_owner.h').read_text()
    boot=(new/'diagnostic_boot.h').read_text()
    assert boot.count('pollBaselineOwner();')==1
    http=(new/'diagnostic_http.h').read_text()
    assert http.index('esp_random()')<http.index('initializeBaselineOwner();')
    assert 'register_baseline_only_routes(server,*rocellBaselineOwner)' in http


def test_startup_candidate_is_separate_and_exclusive():
    root=Path(__file__).resolve().parents[2]/'.firmware-tools'
    previous=root/'configured-diagnostic-candidate-r3/RoArm-M3_example'
    startup=root/'configured-diagnostic-candidate-r4/RoArm-M3_example'
    old_owner=(previous/'configured_native_owner.h').read_text()
    owner=(startup/'configured_native_owner.h').read_text()
    assert 'rocell_diag::ConfiguredDiagnosticRuntime<' in old_owner
    assert 'rocell_diag::ConfiguredStartupRuntime<' in owner
    assert 'rocell_diag::DiagnosticSessionClaim rocellSessionClaim;' in owner
    routes=(startup/'configured_diagnostic_routes.h').read_text()
    assert '/rocell-startup.json' in routes and '/rocell-startup.key' in routes
    assert '/rocell-diagnostics.json' not in routes and '/rocell-diagnostics.key' not in routes
    assert routes.index('rocellSessionClaim.claim(')<routes.index('LittleFS.open(')
    boot=(startup/'diagnostic_boot.h').read_text()
    assert boot.count('pollBaselineOwner();')==1
    assert 'if(!rocellConfiguredRuntime.exclusive_work())server.handleClient();' in boot
