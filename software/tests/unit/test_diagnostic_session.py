from pathlib import Path
import shutil
import subprocess
import pytest
import json
from rocell.application.servo_diagnostic_simulation import simulate_trace
from rocell.application.servo_diagnostic_decode import decode_trace
from rocell.application.servo_write_evidence import assess_write_evidence
from rocell.application.first_motion_contract import canonical
from rocell.application.servo_transport_export import capture_transport_export,replay_transport_export


def test_finite_session_with_injected_io_failures(tmp_path):
    compiler=shutil.which('clang++')
    if not compiler: pytest.skip('Host compiler unavailable')
    source=Path(__file__).resolve().parents[2]/'firmware/diagnostics/test_diagnostic_session.cpp'
    executable=tmp_path/'session-test.exe'
    build=subprocess.run([compiler,'-std=c++14','-Wall','-Wextra','-Werror',str(source),
        '-o',str(executable)],capture_output=True,text=True,timeout=60)
    assert build.returncode==0,build.stderr
    run=subprocess.run([str(executable)],capture_output=True,text=True,timeout=10)
    assert run.returncode==0,run.stderr
    converted,hook,dispatch,write,*pairs=map(json.loads,run.stdout.splitlines())
    assert converted['wire_count']==2100
    assert converted['schema']=='rocell.converted_command.v2'
    assert converted['sample_count']==3 and converted['sample_interval_us']==1000000
    assert hook['status']=='WRITE_VERIFIED'
    assert assess_write_evidence(write,dispatch)['acknowledgment_verified']
    trace=simulate_trace('paired_arrival')
    trace['command']['servo_id']=14
    trace['dispatch']=dispatch
    trace['samples']=pairs
    assessment=decode_trace(canonical(trace))['assessment']
    assert assessment['fresh_position_samples']==3
    assert assessment['category']=='DIAGNOSTIC_ENDPOINT_CRITERIA_MET'
    assert not assessment['progression_authority']
    # Exercise actual producer records through the read-only transport and durable
    # export path, not just a separately handwritten JSON fixture.
    records=[converted,hook,dispatch,write,*pairs]
    def get(path,*,maximum_bytes,timeout_seconds):
        if path.endswith('/status'):
            return canonical(dict(schema='rocell.diagnostic_transport.v2',instance_id='a'*32,
                state='CAPTURED',reason='NONE',records=len(records),storage_fault=False,
                start_supported=False,durable_export_verified=False))
        index=int(path.split('index=')[1])
        return canonical(dict(schema='rocell.diagnostic_record.v2',instance_id='a'*32,
            index=index,kind=('converted','hook','dispatch','write')[index] if index<4 else 'pair',
            record=records[index]))
    exported=capture_transport_export(tmp_path/'exports',get)
    folder=Path(exported['export_path'])
    replay=replay_transport_export(folder.parent,folder.name)
    assert [item['record'] for item in replay['summary']['records']]==records
    assert exported['replay_verified'] and not exported['progression_authority']
