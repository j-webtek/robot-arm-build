import pytest
from rocell.application.first_motion_contract import canonical
from rocell.application.servo_diagnostic_simulation import simulate_trace
from rocell.application.servo_planned_run import collect_planned_run,replay_planned_run
from pathlib import Path


def inputs():
    trace=simulate_trace('paired_arrival');trace['command']['servo_id']=14
    return trace['command'],trace['policy'],canonical(trace['command']['payload']),dict(
        sample_count=3,sample_interval_us=1000000,maximum_lateness_us=1000000,maximum_pair_us=1000)


def idle(path,**kwargs):
    return canonical(dict(schema='rocell.diagnostic_transport.v2',instance_id='a'*32,
        state='IDLE',reason='NONE',records=0,storage_fault=False,start_supported=False,durable_export_verified=False))


def test_plan_export_failure_prevents_all_reads(tmp_path,monkeypatch):
    from rocell.application import servo_planned_run as module
    calls=[]
    monkeypatch.setattr(module,'_read',lambda *args: (_ for _ in ()).throw(ValueError('Failed verification')))
    with pytest.raises(ValueError):collect_planned_run(tmp_path,lambda *a,**k:calls.append(a),*inputs(),origin='SIMULATION')
    assert calls==[]


def test_incomplete_evidence_exports_rejection_and_replays(tmp_path):
    result=collect_planned_run(tmp_path,idle,*inputs(),origin='SIMULATION')
    assert result['outcome']==dict(status='EVIDENCE_REJECTED',assessment=None)
    assert result['export_verified'] and result['replay_verified']
    assert not result['progression_authority']
    plan=tmp_path/result['plan_export_id']/'attachment-session-plan.json'
    plan.write_text('{}')
    with pytest.raises(ValueError):replay_planned_run(tmp_path,Path(result['export_path']).name)
