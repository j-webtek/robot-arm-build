import json
from pathlib import Path
import shutil
import pytest
from rocell.application.ghost_endpoint_rehearsal import rehearse_ghost_endpoints
from rocell.application.wizard_worker import run
from test_arrival_wizard_service import make_service, _run
from test_movement_campaign_ui import render


@pytest.fixture
def workspace(tmp_path):
    path=tmp_path/'software/config'
    path.mkdir(parents=True)
    source=Path(__file__).resolve().parents[3]/'software/config/ghost_keyboard_v1.json'
    shutil.copy2(source,path/source.name)
    return tmp_path


def test_complete_sequence_uses_one_write_per_nonzero_leg(workspace):
    r=rehearse_ghost_endpoints(workspace)
    assert r['status']=='SIMULATED_SEQUENCE_COMPLETE'
    assert len(r['trial_results'])==11 and r['no_motion_leg_sequences']==[0]
    assert r['skipped_trial_ids']==[]
    assert all(len(row['simulated_wire_writes'])==1 for row in r['trial_results'])
    for mapping,row,trial in zip(r['trial_mapping'],r['trial_results'],r['plan']['trials']):
        command=json.loads(row['simulated_wire_writes'][0])
        assert command['T']==104
        assert command['z']==trial['target']['z_mm']
        assert mapping['trial_id']==trial['trial_id']
    assert r['native_device_opens']==r['physical_motion_commands']==0
    assert not r['physical_authority'] and not r['camera_required']


@pytest.mark.parametrize('fault',[
    'BASELINE_MISMATCH','SHORT_WRITE','UNCHANGED','CANCEL_AFTER_WRITE','CLEANUP_PENDING',
    'MISSING_FEEDBACK','POSITION_BIAS'])
@pytest.mark.parametrize('fault_trial',range(1,12))
def test_fault_at_each_leg_skips_all_following_legs(workspace,fault,fault_trial):
    # Exercise approach, press and retract boundaries, including the first and
    # final command. A fault must never dispatch a recovery return or next key.
    r=rehearse_ghost_endpoints(workspace,fault=fault,fault_trial=fault_trial)
    assert r['status']=='SIMULATED_SEQUENCE_STOPPED'
    assert len(r['trial_results'])==fault_trial
    assert len(r['skipped_trial_ids'])==11-fault_trial
    assert all(row['trial']['status']=='OBSERVED_ENDPOINT_DWELL'
               for row in r['trial_results'][:-1])
    failed=r['trial_results'][-1]
    assert failed['fault']==fault and failed['trial']['status']!='OBSERVED_ENDPOINT_DWELL'
    assert len(failed['simulated_wire_writes'])==(0 if fault=='BASELINE_MISMATCH' else 1)
    assert not r['automatic_retry_allowed']
    assert r['native_device_opens']==r['physical_motion_commands']==0


def test_repeated_keys_preserved_but_zero_travel_not_dispatched(workspace):
    r=rehearse_ghost_endpoints(workspace,'aaa')
    assert len(r['trial_results'])==9
    assert r['no_motion_leg_sequences']==[0,4,8]


def test_delayed_arrival_still_completes_without_resending(workspace):
    r=rehearse_ghost_endpoints(workspace,fault='DELAYED_ARRIVAL',fault_trial=2)
    assert r['status']=='SIMULATED_SEQUENCE_COMPLETE'
    assert len(r['trial_results'])==11
    delayed=r['trial_results'][1]
    assert delayed['synthetic_observation_model']['arrival_delay_s']==.35
    assert not delayed['synthetic_observation_model']['servo_acquisition_freshness_verified']
    assert len(delayed['simulated_wire_writes'])==1


@pytest.mark.parametrize('index',[0,12,2.5,True])
def test_bad_fault_index_rejected_without_attempt(workspace,index):
    with pytest.raises(ValueError): rehearse_ghost_endpoints(workspace,fault_trial=index)
    assert not (workspace/'software/runs/endpoint-rehearsals').exists()


@pytest.mark.parametrize('mode',['physical','rehearsal'])
def test_wizard_result_export(make_service,workspace,mode):
    service,runner,_=make_service(mode=mode)
    runner.run=lambda action,values,**kw:run(workspace,action,values,kw['cell_id'])
    op=_run(service,'rehearse_ghost_endpoints',dict(text='aba',fault='SHORT_WRITE',fault_trial=2))
    assert op['status']=='SUCCEEDED'  # Completed simulation, not successful motion.
    assert op['result']['motion_command_count']==0
    assert 'SIMULATED_SEQUENCE_STOPPED' in render(op)
    exported=_run(service,'export_logs')
    assert exported['status']=='SUCCEEDED'
    path=Path(exported['result']['receipt']['path'])/f"attachment-result-{op['operation_id'].removeprefix('operation-')}.json"
    assert json.loads(path.read_bytes())==op['result']
