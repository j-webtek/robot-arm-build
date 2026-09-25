from pathlib import Path
import pytest
from rocell.application.shoulder_characterization_sim import run_characterization_sim,FAULTS
from rocell.application.wizard_diagnostic_export import verify_export


@pytest.mark.parametrize('residual,status',[((9,-7),'SETTLED_MISS'),((0,0),'SETTLED_ACCURATE')])
def test_twelve_legs_follow_measured_state_and_verified_predecessor(tmp_path,residual,status):
    result=run_characterization_sim(tmp_path,residual=residual);report=result['report']
    assert report['state']=='COMPLETED' and report['completed_measurements']==12
    assert report['simulated_packets']==12 and report['physical_packets']==0
    for index,row in enumerate(report['legs']):
        assert row['assessment']['status']==status
        if index:
            previous=report['legs'][index-1]
            assert row['predecessor_export']==previous['result_export']
            assert row['baseline']['positions']==previous['samples'][-1]['positions']
            assert row['baseline']['started_us']>previous['samples'][-1]['finished_us']
    assert all(verify_export(Path(p))['valid'] for p in report['exports'])


@pytest.mark.parametrize('fault',[f for f in FAULTS if f!='NONE'])
def test_fault_on_fourth_leg_prevents_fifth_packet(tmp_path,fault):
    result=run_characterization_sim(tmp_path,fault=fault,fault_leg=4);report=result['report']
    assert report['state']=='STOPPED' and len(report['legs'])==4
    assert report['simulated_packets']==(3 if fault in ('BASELINE_DRIFT','CANCELLED') else 4)
    assert report['physical_packets']==0 and report['completed_measurements']==3
    assert verify_export(Path(result['export_path']))['valid']


def test_invalid_scenario_cannot_export_or_dispatch(tmp_path):
    with pytest.raises(ValueError):run_characterization_sim(tmp_path,fault='UNKNOWN')
    assert not list(tmp_path.iterdir())
