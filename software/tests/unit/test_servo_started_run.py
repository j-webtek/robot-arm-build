from pathlib import Path
import pytest
from rocell.application.first_motion_contract import canonical
from rocell.application.servo_prepared_start import send_prepared_start
from rocell.application.servo_started_run import collect_started_run,replay_started_run
from test_servo_prepared_start import Sender
from test_servo_diagnostic_start_http import native_plan,KEY


def test_uncertain_send_links_fault_capture_without_another_send(tmp_path):
    plan,challenge=native_plan();sender=Sender(tmp_path,True)
    prepared=send_prepared_start(tmp_path,sender,plan,challenge,KEY)
    reads=[]
    def reader(path,**kwargs):
        reads.append(path)
        return canonical(dict(schema='rocell.diagnostic_transport.v3',instance_id=challenge['boot_id'],
            state='FAULT',reason='INTERFERING_COMMAND',records=0,storage_fault=False,
            start_supported=True,durable_export_verified=False))
    result=collect_started_run(tmp_path,Path(prepared['export_path']).name,reader)
    assert sender.calls==1 and len(reads)==2
    assert result['outcome']['status']=='EVIDENCE_REJECTED'
    assert result['export_verified'] and result['replay_verified']
    assert replay_started_run(tmp_path,Path(result['export_path']).name)['matches']
    (tmp_path/prepared['claim_file']).write_bytes(b'{')
    with pytest.raises(ValueError):replay_started_run(tmp_path,Path(result['export_path']).name)


def test_invalid_claim_blocks_collection_before_network(tmp_path):
    plan,challenge=native_plan();prepared=send_prepared_start(tmp_path,Sender(tmp_path),plan,challenge,KEY)
    (tmp_path/prepared['claim_file']).write_bytes(b'{}');reads=[]
    with pytest.raises(ValueError):collect_started_run(tmp_path,Path(prepared['export_path']).name,
        lambda *args,**kwargs:reads.append(args))
    assert reads==[]
