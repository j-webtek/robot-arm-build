import json
from pathlib import Path
import shutil
import subprocess
import pytest


def test_actual_readonly_handlers(tmp_path):
    compiler=shutil.which('clang++')
    if not compiler: pytest.skip('Host compiler unavailable')
    source=Path(__file__).resolve().parents[2]/'firmware/diagnostics/test_diagnostic_http.cpp'
    executable=tmp_path/'http-test.exe'
    build=subprocess.run([compiler,'-std=c++14','-Wall','-Wextra','-Werror',str(source),
        '-o',str(executable)],capture_output=True,text=True,timeout=60)
    assert build.returncode==0,build.stderr
    run=subprocess.run([str(executable)],capture_output=True,text=True,timeout=10)
    assert run.returncode==0,run.stderr
    status,record=map(json.loads,run.stdout.splitlines())
    assert status['state']=='IDLE' and status['records']==0
    assert not status['start_supported'] and not status['durable_export_verified']
    assert record['index']==0 and record['record']=={'example':1}
    assert status['schema']=='rocell.diagnostic_transport.v2'
    assert len(status['instance_id'])==32 and record['instance_id']==status['instance_id']
