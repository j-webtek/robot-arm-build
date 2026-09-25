import copy
import json
import pytest
from test_product_ghost_controller_bridge import source
from rocell.application.product_ghost_endpoints import rehearse_product_endpoints


def route():
    data=source(); r=data['dense_route']['round']
    third=copy.deepcopy(r['joint_results'][0]); third['waypoint_sequence']=2
    r['joint_results'].append(third)
    r['waypoint_count']=r['evaluated_waypoint_count']=3
    return data


def test_product_route_endpoint_commands_match_plan(tmp_path):
    result=rehearse_product_endpoints(tmp_path,route())
    assert result['status']=='SIMULATED_SEQUENCE_COMPLETE'
    assert len(result['trial_results'])==2
    for trial,row in zip(result['plan']['trials'],result['trial_results']):
        assert len(row['simulated_wire_writes'])==1
        command=json.loads(row['simulated_wire_writes'][0])
        for wire,axis in zip(('x','y','z','t','r','g'),('x_mm','y_mm','z_mm','pitch_rad','roll_rad','gripper_rad')):
            assert command[wire]==trial['target'][axis]
    assert not result['physical_authority']


@pytest.mark.parametrize('fault',['BASELINE_MISMATCH','SHORT_WRITE','UNCHANGED','MISSING_FEEDBACK','POSITION_BIAS'])
def test_fault_stops_before_following_leg(tmp_path,fault):
    result=rehearse_product_endpoints(tmp_path,route(),fault=fault,fault_trial=1)
    assert result['status']=='SIMULATED_SEQUENCE_STOPPED'
    assert len(result['trial_results'])==1 and len(result['skipped_trial_ids'])==1
    assert result['physical_motion_commands']==0


@pytest.mark.parametrize('index',[0,3,True,1.5])
def test_invalid_index_never_runs(tmp_path,index):
    with pytest.raises(ValueError):
        rehearse_product_endpoints(tmp_path,route(),fault_trial=index)
    assert not (tmp_path/'software/runs/endpoint-rehearsals').exists()


def test_failed_interpolation_prevents_runner(tmp_path,monkeypatch):
    import rocell.application.product_ghost_endpoints as module
    monkeypatch.setattr(module,'screen_product_ghost',lambda source: {'status':'REFERENCE_INTERPOLATION_INCOMPLETE'})
    with pytest.raises(ValueError): rehearse_product_endpoints(tmp_path,route())
    assert not (tmp_path/'software/runs/endpoint-rehearsals').exists()
