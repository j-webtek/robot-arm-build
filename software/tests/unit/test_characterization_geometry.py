"""Actual nominal scene, synthetic transforms; never physical clearance proof."""

from pathlib import Path
import pytest

from rocell.motion.characterization_geometry import check_campaign_geometry
from rocell.motion.characterization_plan import freeze_campaign
from rocell.models.frames import Transform
from rocell.simulation.scene import load_rc03_nominal_scene
from test_characterization_plan import candidate


@pytest.fixture
def scene():
    return load_rc03_nominal_scene(Path(__file__).resolve().parents[3]/'active-project/RoCell_v0_3')


def translated(frame,x,y,z):
    return Transform('board',frame,(1,0,0,x,0,1,0,y,0,0,1,z,0,0,0,1))


def bound(data,scene,transform):
    report=check_campaign_geometry(freeze_campaign(data),scene,transform,clearance_mm=5)
    data['evidence']['geometry_sha256']=report['geometry_sha256']
    return freeze_campaign(data)


def test_missing_transform_is_unknown_not_identity(scene):
    r=check_campaign_geometry(freeze_campaign(candidate()),scene,None,clearance_mm=5)
    assert r['status']=='TRANSFORM_REQUIRED'
    assert r['trial_checks']==[]
    assert r['obstacle_count']>0
    assert all(n>0 for n in r['board_size_mm'])


def test_explicit_bound_far_path_is_only_nominal_tip_clear(scene):
    data=candidate(); transform=translated('robot_base',0,0,10000)
    plan=bound(data,scene,transform)
    r=check_campaign_geometry(plan,scene,transform,clearance_mm=5)
    assert r['status']=='NOMINAL_TIP_PATH_CLEAR_ONLY'
    assert r['trial_checks'][0]['start_board_mm']==[0,0,10000]
    assert r['full_link_clearance']=='UNKNOWN'
    assert not r['physical_ready']
    changed=check_campaign_geometry(plan,scene,transform,clearance_mm=6)
    assert changed['status']=='GEOMETRY_BINDING_MISMATCH'


def test_obstacle_contact_is_not_exempt_for_noncontact_campaign(scene):
    obstacle=scene.obstacles[0]
    center=[(getattr(obstacle.minimum,a)+getattr(obstacle.maximum,a))/2 for a in ('x','y','z')]
    transform=translated('robot_base',*center)
    plan=bound(candidate(),scene,transform)
    r=check_campaign_geometry(plan,scene,transform,clearance_mm=5)
    assert r['status']=='NOMINAL_TIP_COLLISION'
    assert obstacle.obstacle_id in r['trial_checks'][0]['collisions']


def test_controller_and_model_frame_are_not_aliases(scene):
    data=candidate(); data['frame']='R_ctrl'
    plan=freeze_campaign(data)
    with pytest.raises(ValueError):
        check_campaign_geometry(plan,scene,translated('robot_base',0,0,10000),clearance_mm=5)
    assert plan.to_dict()['frame']=='R_ctrl'


def test_nominal_collision_prevents_simulated_trial_and_return(scene):
    from rocell.motion.characterization_sim import simulate_campaign
    plan=freeze_campaign(candidate())
    result=simulate_campaign(plan,travel_s=.5,sample_period_s=.05,blocked_trial_ids=('out',))
    assert result['status']=='STOPPED'
    assert result['trial_results'][0]['status']=='NOMINAL_GEOMETRY_BLOCKED'
    assert result['trial_results'][0]['samples']==[]
    assert result['skipped_trial_ids']==['back']
