from pathlib import Path
import pytest
from test_compensated_wrist_cycle import adapters
from test_product_ghost_controller_bridge import source
from rocell.application.compensated_wrist_cycle import CompensatedWristCycle
from rocell.application.wrist_tip_review import review_wrist_tip
from rocell.geometry import UrdfModel


def inputs():
    leg,_,_=adapters();reports=[]
    def publish(**kw):
        reports.append(kw['report']);return dict(verified=True,export='sample')
    CompensatedWristCycle().run(run_leg=leg,publish_leg=publish)
    model=UrdfModel.from_file(Path(__file__).resolve().parents[3]/'software/models/roarm_m3/roarm_m3_kinematic_40dbd84.urdf')
    return reports,source(),model


def test_model_review_preserves_frames_and_cycle_closure():
    r=review_wrist_tip(*inputs())
    assert r['modeled_cycle_closure_mm']<1e-8
    assert not r['physical_accuracy_verified'] and not r['motion_authorized']
    assert not r['keyboard_route_relocated'] and r['frame']=='VENDOR_BASE_UNREGISTERED'
    assert all(len(leg['modeled_arc_samples'])==41 for leg in r['legs'])
    assert r['legs'][0]['vertical_travel_mm']*r['legs'][1]['vertical_travel_mm']<0


def test_failed_leg_not_geometry_evidence():
    reports,ghost,model=inputs();reports[0]['run']['error']='FAULT'
    with pytest.raises(ValueError):review_wrist_tip(reports,ghost,model)


def test_park_is_not_mislabeled_as_first_key_hover():
    reports,ghost,model=inputs()
    ghost['dense_route']['round']['joint_results'][0].update(phase='PARK',semantic_target=None)
    r=review_wrist_tip(reports,ghost,model)
    assert r['route_entry_phase']=='PARK'
    assert r['first_ghost_phase']=='HOVER' and r['first_ghost_key']=='keyboard:A'
    assert r['route_entry_tip_mm']!=r['first_ghost_tip_mm']
