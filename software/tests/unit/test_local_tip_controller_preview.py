from pathlib import Path
import pytest
from rocell.geometry import UrdfModel
from rocell.application import local_tip_controller_preview as module


def test_controller_path_preserves_tool_cycle_without_motion_authority():
    model=UrdfModel.from_file(Path(__file__).resolve().parents[3]/'software/models/roarm_m3/roarm_m3_kinematic_40dbd84.urdf')
    q=[.001533981,.033747577,1.636757501,-.052155347,.018407769,3.138524692]
    r=module.preview_local_tip_controller(model,q)
    assert r['status']=='CONTROLLER_REFERENCE_PASS_NOT_EXECUTABLE'
    assert len(r['legs'])==8
    assert r['maximum_lateral_drift_mm']<=.05
    assert all(s['joints_rad'][5]==q[5] for leg in r['legs'] for s in leg['samples'])
    assert not r['motion_authorized'] and not r['compensation_applied']
    assert r['hardware_commands_generated']==0
    assert r['legs'][-1]['samples'][-1]['tip_mm']==pytest.approx(r['local_reference']['start_tip_mm'],abs=1e-6)
    for leg in r['legs']:
        assert leg['samples'][0]['fraction']==0
        assert leg['samples'][-1]['fraction']==1


def test_current_posture_exposes_decreasing_elbow_on_retraction():
    model=UrdfModel.from_file(Path(__file__).resolve().parents[3]/'software/models/roarm_m3/roarm_m3_kinematic_40dbd84.urdf')
    q=[.001533981,.033747577,1.691980809,-.052155347,.018407769,3.138524692]
    r=module.preview_local_tip_controller(model,q)
    assert r['status']=='CONTROLLER_REFERENCE_PASS_NOT_EXECUTABLE'
    press,retract=r['joint_motion_demands']
    assert press['phase']=='PRESS' and retract['phase']=='RETRACT'
    assert press['joints'][2]['direction']=='INCREASING'
    assert retract['joints'][2]['direction']=='DECREASING'
    assert 7<press['joints'][2]['nominal_encoder_steps']<9
    assert abs(press['joints'][1]['nominal_encoder_steps'])<1
    for a,b in zip(press['joints'],retract['joints']):
        assert a['delta_rad']==pytest.approx(-b['delta_rad'])
    assert r['nominal_encoder_steps_are_not_servo_response_predictions']
    assert not r['motion_authorized']


def test_intermediate_limit_failure_rejects_route(monkeypatch):
    model=UrdfModel.from_file(Path(__file__).resolve().parents[3]/'software/models/roarm_m3/roarm_m3_kinematic_40dbd84.urdf')
    def reject(state):
        raise ValueError('Injected provisional limit failure')
    monkeypatch.setattr(module,'validate_provisional_simulation_intersection',reject)
    r=module.preview_local_tip_controller(model,[.001533981,.033747577,1.636757501,-.052155347,.018407769,3.138524692])
    assert r['status']=='CONTROLLER_REFERENCE_REJECTED'
    assert r['reason']=='Injected provisional limit failure'
    assert not r['motion_authorized']


def test_failed_local_reference_is_not_promoted(monkeypatch):
    monkeypatch.setattr(module,'preview_local_tip_cycle',lambda *args,**kwargs:dict(status='IK_REJECTED'))
    r=module.preview_local_tip_controller(None,[])
    assert r['status']=='LOCAL_REFERENCE_REJECTED' and r['legs']==[]


def test_wrong_inverse_branch_rejects_controller_path(monkeypatch):
    model=UrdfModel.from_file(Path(__file__).resolve().parents[3]/'software/models/roarm_m3/roarm_m3_kinematic_40dbd84.urdf')
    monkeypatch.setattr(module,'inverse',lambda *args:(0,0,0,0))
    r=module.preview_local_tip_controller(model,[.001533981,.033747577,1.636757501,-.052155347,.018407769,3.138524692])
    assert r['status']=='CONTROLLER_REFERENCE_REJECTED'
    assert not r['motion_authorized']
