from test_product_ghost_controller_bridge import source
from test_compensated_elbow_native import baseline
from rocell.application.product_ghost_approach import preview_ghost_approach


def test_approach_preserves_gripper_and_no_authority():
    result=preview_ghost_approach(source(),baseline())
    assert 0<len(result['legs'])<=64
    assert result['starting_controller_pose'][5]==result['target_controller_pose'][5]==3.138524692
    assert not result['motion_authorized'] and not result['compensation_applied']
    assert result['tool_selection']['hand_tcp_to_tip_z_mm']==-100


def test_failure_stops_reference_screening(monkeypatch):
    import rocell.application.product_ghost_approach as module
    monkeypatch.setattr(module,'_screen_reference_trace',lambda trace:dict(status='REJECTED'))
    result=preview_ghost_approach(source(),baseline())
    assert result['status']=='APPROACH_REFERENCE_REJECTED'
    assert len(result['legs'])==1


def test_provisional_limit_failure_is_not_reference_pass(monkeypatch):
    import rocell.application.product_ghost_approach as module
    monkeypatch.setattr(module,'inverse',lambda *args:(0,2,1,0))
    result=preview_ghost_approach(source(),baseline())
    assert result['status']=='APPROACH_REFERENCE_REJECTED'
    assert result['legs'][0]['status']=='PROVISIONAL_JOINT_LIMIT_REJECTED'


def test_hypothetical_tool_sweep_explicitly_unregistered():
    from pathlib import Path
    from rocell.geometry import UrdfModel
    root=Path(__file__).resolve().parents[3]
    model=UrdfModel.from_file(root/'software/models/roarm_m3/roarm_m3_kinematic_40dbd84.urdf')
    result=preview_ghost_approach(source(),baseline(),model=model)
    sweep=result['hypothetical_tip_sweep']
    assert sweep['frame']=='VENDOR_BASE_UNREGISTERED'
    assert not sweep['physical_clearance_verified']
    assert all(lo<=v<=hi for lo,v,hi in zip(sweep['minimum_mm'],sweep['last_mm'],sweep['maximum_mm']))
