import copy
import pytest
from rocell.application.product_ghost_controller_bridge import bridge_product_ghost
from rocell.application.controller_model_baseline import ARM_MAP


def source():
    rows=[]
    for i in range(2):
        rows.append(dict(accepted=True,waypoint_sequence=i,phase='HOVER',semantic_target='keyboard:A',
            action_index=0,achieved_tip_position_board_mm=[100,100,30+i],
            solution_arm_joint_positions_rad=dict(zip((n for _,n in ARM_MAP),[0,.6,1.9-i*.01,-.93,0]))))
    return dict(schema='rocell.static_task_rehearsal.v1',status='DENSE_SAMPLES_PASS_NOT_EXECUTABLE',
        device='keyboard',physical_authority=False,tool_selection=dict(hand_tcp_to_tip_z_mm=-100),
        plan_hash='a'*64,source_hashes={},dense_route=dict(round=dict(all_waypoints_accepted=True,
            waypoint_count=2,evaluated_waypoint_count=2,joint_results=rows)))


def test_firmware_projection_keeps_tip_frame_distinct():
    data=source(); before=copy.deepcopy(data)
    result=bridge_product_ghost(data)
    assert len(result['legs'])==1
    assert result['maximum_inverse_roundtrip_rad']<1e-6
    assert result['samples'][0]['controller_reference_xyz_pitch'][:3]!=[100,100,30]
    assert not result['controller_model_correlation_verified']
    assert not result['motion_authorized'] and not result['approach_from_live_pose_included']
    assert data==before
    assert result==bridge_product_ghost(data)


@pytest.mark.parametrize('case',['failed','partial','tool','nonfinite','sequence','authority'])
def test_invalid_input_never_becomes_reference_route(case):
    data=source(); route=data['dense_route']['round']
    if case=='failed': route['joint_results'][1]['accepted']=False
    if case=='partial': route['waypoint_count']=3
    if case=='tool': data['tool_selection']['hand_tcp_to_tip_z_mm']=-80
    if case=='nonfinite': route['joint_results'][0]['solution_arm_joint_positions_rad'][ARM_MAP[0][1]]=float('nan')
    if case=='sequence': route['joint_results'][1]['waypoint_sequence']=0
    if case=='authority': data['physical_authority']=True
    with pytest.raises(ValueError): bridge_product_ghost(data)
