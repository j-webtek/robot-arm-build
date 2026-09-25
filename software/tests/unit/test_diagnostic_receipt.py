import json
from pathlib import Path
import shutil
import subprocess
import pytest


def test_native_receipt_parser_preserves_exact_payload(tmp_path):
    compiler=shutil.which('clang++')
    if not compiler:pytest.skip('Host compiler unavailable')
    root=Path(__file__).resolve().parents[2]
    source=root/'firmware/diagnostics/test_diagnostic_receipt.cpp'
    include=root/'.firmware-tools/user/libraries/ArduinoJson/src'
    executable=tmp_path/'receipt-test.exe'
    build=subprocess.run([compiler,'-std=c++14','-Wall','-Wextra','-Werror','-I'+str(include),
        str(source),'-o',str(executable)],capture_output=True,text=True,timeout=60)
    assert build.returncode==0,build.stderr
    run=subprocess.run([str(executable)],capture_output=True,text=True,timeout=10)
    assert run.returncode==0,run.stderr
    receipt=json.loads(run.stdout)
    assert receipt['payload_utf8']==' {"T":101, "joint":3,"rad":1.7,"spd":20,"acc":1} \n'
    assert receipt['received_rad']==pytest.approx(1.7) and receipt['command_id']=='command'
    assert float(receipt['received_rad_text'])==1.7000000476837158
