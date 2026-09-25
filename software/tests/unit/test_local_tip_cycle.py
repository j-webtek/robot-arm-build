from pathlib import Path
import pytest
from rocell.geometry import UrdfModel
from rocell.application.local_tip_cycle import preview_local_tip_cycle


def test_coordinated_vertical_tip_cycle_is_model_only():
    model=UrdfModel.from_file(Path(__file__).resolve().parents[3]/'software/models/roarm_m3/roarm_m3_kinematic_40dbd84.urdf')
    q=[.001533981,.033747577,1.636757501,-.052155347,.018407769,3.138524692]
    r=preview_local_tip_cycle(model,q)
    assert r['status']=='LOCAL_TIP_REFERENCE_PASS_NOT_EXECUTABLE'
    assert len(r['waypoints'])==9 and r['interpolated_samples']==168
    assert r['maximum_lateral_drift_mm']<=.05 and r['modeled_return_error_mm']<1e-8
    assert r['maximum_vertical_tracking_error_mm']<=.02
    assert r['waypoints'][4]['tip_mm'][2]==pytest.approx(r['start_tip_mm'][2]-2,abs=.02)
    assert r['waypoints'][-1]['joints_rad']==q
    assert not r['motion_authorized'] and not r['keyboard_route_relocated']
    assert all(w['joints_rad'][5]==q[5] for w in r['waypoints'])


@pytest.mark.parametrize('q',[[0]*5,[0,0,float('nan'),0,0,0],[0,0,0,0,0,True]])
def test_invalid_pose_cannot_produce_a_preview(q):
    with pytest.raises(ValueError,match='Six finite joints'):
        preview_local_tip_cycle(None,q)


def test_ik_failure_does_not_publish_an_executable_or_successful_path(monkeypatch):
    from types import SimpleNamespace
    from rocell.application import local_tip_cycle
    monkeypatch.setattr(local_tip_cycle.RoArmM3NumericalIk,'solve',
                        lambda *args,**kwargs:SimpleNamespace(solution_arm_joint_positions=()))
    model=UrdfModel.from_file(Path(__file__).resolve().parents[3]/'software/models/roarm_m3/roarm_m3_kinematic_40dbd84.urdf')
    r=preview_local_tip_cycle(model,[.001533981,.033747577,1.636757501,-.052155347,.018407769,3.138524692])
    assert r['status']=='IK_REJECTED' and r['waypoints']==[]
    assert not r['motion_authorized'] and r['hardware_commands_generated']==0


def test_upward_reference_has_separate_direction_and_does_not_authorize_return():
    model=UrdfModel.from_file(Path(__file__).resolve().parents[3]/'software/models/roarm_m3/roarm_m3_kinematic_40dbd84.urdf')
    q=[.001533981,.033747577,1.670505078,-.064427193,.018407769,3.138524692]
    r=preview_local_tip_cycle(model,q,direction='retract')
    assert r['status']=='LOCAL_TIP_REFERENCE_PASS_NOT_EXECUTABLE'
    assert r['waypoints'][4]['tip_mm'][2]==pytest.approx(r['start_tip_mm'][2]+2,abs=.02)
    assert r['waypoints'][4]['phase']=='RETRACT'
    assert r['waypoints'][-1]['joints_rad']==q
    assert not r['motion_authorized']
    with pytest.raises(ValueError):preview_local_tip_cycle(model,q,direction='anything')
