import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import pytest


def test_exact_reference_conversion_without_bus_write(tmp_path):
    root=Path(__file__).resolve().parents[2]
    tools=root/'.firmware-tools'
    path=tools/'reference/RoArm-M3_example/RoArm-M3_module.h'
    raw=path.read_bytes()
    manifest=json.loads((tools/'reference-build-inputs.json').read_text())
    assert hashlib.sha256(raw).hexdigest()==manifest['files'][str(path.relative_to(tools))]
    text=raw.decode('utf-8-sig').replace('\r\r\n','\n').replace('\r\n','\n')
    bodies=[]
    for signature in ('double calculatePosByRad(', 'int RoArmM3_elbowJointCtrlRad('):
        start=text.index(signature);end=text.index('\n}',start)+2
        bodies.append(text[start:end])
    # Test-generated reference fixture only; production source is never rewritten.
    (tmp_path/'pinned_elbow_functions.h').write_text('\n'.join(bodies))
    compiler=shutil.which('clang++')
    if not compiler:pytest.skip('Host compiler unavailable')
    source=root/'firmware/diagnostics/test_reference_elbow_admission.cpp'
    executable=tmp_path/'admission-test.exe'
    build=subprocess.run([compiler,'-std=c++14','-Wall','-Wextra','-Werror','-I'+str(tmp_path),
        '-I'+str(tools/'user/libraries/ArduinoJson/src'),
        str(source),'-o',str(executable)],capture_output=True,text=True,timeout=60)
    assert build.returncode==0,build.stderr
    run=subprocess.run([str(executable)],capture_output=True,text=True,timeout=10)
    assert run.returncode==0,run.stderr
    converted,dispatch=map(json.loads,run.stdout.splitlines())
    assert converted['wire_count']==dispatch['wire_count']==2132
    assert converted['command_id']==dispatch['command_id']=='native-conversion'
