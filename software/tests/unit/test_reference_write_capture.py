import json
from pathlib import Path
import shutil
import subprocess
import pytest
from rocell.application.servo_write_evidence import assess_write_evidence


def test_actual_write_hook_with_inert_bus(tmp_path):
    compiler=shutil.which('clang++')
    if not compiler: pytest.skip('Host compiler unavailable')
    source=Path(__file__).resolve().parents[2]/'firmware/diagnostics/test_reference_write_capture.cpp'
    executable=tmp_path/'write-test.exe'
    build=subprocess.run([compiler,'-std=c++14','-Wall','-Wextra','-Werror',str(source),
        '-o',str(executable)],capture_output=True,text=True,timeout=60)
    assert build.returncode==0,build.stderr
    run=subprocess.run([str(executable)],capture_output=True,text=True,timeout=10)
    assert run.returncode==0,run.stderr
    dispatch,write,*outcomes=map(json.loads,run.stdout.splitlines())
    assert dispatch['wire_count']==2100
    assert assess_write_evidence(write,dispatch)['acknowledgment_verified']
    assert [item['status'] for item in outcomes]==[
        'WRITE_VERIFIED','WRITE_NOT_VERIFIED','WRITE_NOT_VERIFIED',
        'WRITE_NOT_VERIFIED','INVALID_CLOCK','REJECTED_INPUT']
    assert outcomes[4]['capture_stopped']
    assert int(outcomes[4]['finished_us_raw']) < int(outcomes[4]['started_us_raw'])
    assert not outcomes[5]['write_attempted']
