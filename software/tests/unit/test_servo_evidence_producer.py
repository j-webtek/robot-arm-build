"""Compile/run portable producer with an injected bus, then ingest its output.

No serial/network adapter is linked to the C++ test executable.
"""
from pathlib import Path
import shutil
import json
import subprocess
import pytest
from rocell.application.servo_diagnostic_simulation import simulate_trace
from rocell.application.servo_diagnostic_decode import decode_trace
from rocell.application.first_motion_contract import canonical
from rocell.application.servo_write_evidence import assess_write_evidence


def test_cpp_producer_output_enters_host_decoder(tmp_path):
    compiler=shutil.which('clang++')
    if not compiler:pytest.skip('Host C++ compiler unavailable; producer not validated here')
    source=Path(__file__).resolve().parents[2]/'firmware'/'diagnostics'/'test_servo_evidence.cpp'
    executable=tmp_path/'producer-test.exe'
    subprocess.run([compiler,'-std=c++14','-Wall','-Wextra','-Werror',str(source),
        '-o',str(executable)],check=True,capture_output=True,text=True,timeout=60)
    result=subprocess.run([str(executable)],check=True,capture_output=True,text=True,timeout=10)
    lines=result.stdout.splitlines()
    assert len(lines)==5
    trace=simulate_trace('paired_arrival')
    trace['command']['servo_id']=14;trace['dispatch']['servo_id']=14
    pair=json.loads(lines[0])
    trace['samples']=[pair]
    decoded=decode_trace(canonical(trace))
    assert decoded['assessment']['fresh_position_samples']==1
    assert decoded['assessment']['matching_target_readback_observed']
    assert decoded['assessment']['final_desired_error_counts']==0
    # One successful sample is not a settled endpoint, much less live authority.
    assert decoded['assessment']['category']=='FRESH_POSITION_NOT_SETTLED_AT_DESIRED_TARGET'
    assert not decoded['assessment']['progression_authority']
    # Consume the failed C++ acquisition verbatim too: no test-side reconstruction
    # of identities, addresses, read validity or byte arrays.
    failure=json.loads(lines[1])
    assert failure['feedback']['raw_hex'] is None
    trace['samples']=[pair,failure]
    assessed=decode_trace(canonical(trace))['assessment']
    assert assessed['category']=='DIAGNOSTIC_EVIDENCE_INCOMPLETE_OR_CONTRADICTORY'
    assert assessed['fresh_position_samples']==1
    assert assessed['final_desired_error_counts'] is None
    trace['samples']=[json.loads(lines[2])]
    trace['dispatch']=json.loads(lines[3])
    assert trace['dispatch']['command_id']=='simulation-command'
    assert trace['dispatch']['servo_id']==14
    assert decode_trace(canonical(trace))['assessment']['fresh_position_samples']==1
    write = assess_write_evidence(json.loads(lines[4]), trace['dispatch'])
    assert write['acknowledgment_verified']
    assert not write['progression_authority']
