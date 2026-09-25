from pathlib import Path
import shutil
import subprocess
import pytest


@pytest.mark.parametrize('configured',[False,True,'recovery'])
def test_actual_diagnostic_boot_with_inert_dependencies(tmp_path,configured):
    compiler=shutil.which('clang++')
    if not compiler:pytest.skip('Host compiler unavailable')
    root=Path(__file__).resolve().parents[2]
    executable=tmp_path/'boot-test.exe'
    result=subprocess.run([compiler,'-std=c++14','-Wall','-Wextra','-Werror',
        *(['-DROCELL_CONFIGURED_DIAGNOSTIC_OWNER=1'] if configured else []),
        *(['-DROCELL_RECOVERY_DIAGNOSTIC_OWNER=1'] if configured=='recovery' else []),
        '-I'+str(root/'.firmware-tools/user/libraries/ArduinoJson/src'),
        str(root/'firmware/diagnostics/test_diagnostic_boot.cpp'),'-o',str(executable)],
        capture_output=True,text=True,timeout=60)
    assert result.returncode==0,result.stderr
    for scenario in range(7):
        run=subprocess.run([str(executable),str(scenario)],capture_output=True,text=True,timeout=10)
        assert run.returncode==0,(scenario,run.stderr)


@pytest.mark.parametrize('target',['diagnostic-boot-candidate','configured-diagnostic-candidate','configured-diagnostic-candidate-r2'])
def test_generated_sketch_replaces_legacy_entry_points(target):
    root=Path(__file__).resolve().parents[2]
    folder=root/'.firmware-tools'/target/'RoArm-M3_example'
    sketch=(folder/'RoArm-M3_example.ino').read_text()
    assert '#include "diagnostic_boot.h"' in sketch
    assert 'void setup()' not in sketch and 'void loop()' not in sketch
    assert 'missionPlay(' not in sketch and 'RoArmM3_resetPID(' not in sketch
    boot=(root/'firmware/diagnostics/diagnostic_boot.h').read_bytes()
    if target.startswith('configured-diagnostic-candidate'):
        assert (folder/'diagnostic_boot.h').read_bytes()==boot
        assert '#include "configured_native_owner.h"' in sketch
        assert '#include "native_diagnostic_owner.h"' not in sketch
        if target.endswith('-r2'):
            session=(folder/'diagnostic_session.h').read_bytes()
            assert session==(root/'firmware/diagnostics/diagnostic_session.h').read_bytes()
            assert b'TARGET_READBACK_MISMATCH' in session
    else:
        # Retain the older build unchanged, rather than overwrite audited inputs.
        assert '#include "native_diagnostic_owner.h"' in sketch
        assert 'rocellConfiguredRuntime' not in (folder/'diagnostic_boot.h').read_text()
