import pytest
from rocell.application.pose_policy_review import compare_pose_policy


def inputs():
    positions=[2047,2455,1659,2906,1589,2040,2047]
    pose=dict(origin='DEVICE_CAPTURE',category='STABLE_SAMPLED_POSE',joints=[
        dict(servo_id=11+i,last_position=p,last_goal=2907 if i==3 else 0,torque=int(i==3))
        for i,p in enumerate(positions)])
    hold=dict(hold_policy=dict(joints=[[2045,2049],[2485,2489],[1627,1631],[2893,2909],
        [2033,2037],[2039,2043],[2052,2056]]))
    return pose,hold,dict(offset_counts=10)


def test_changed_pose_cannot_reuse_installed_windows():
    report=compare_pose_policy(*inputs())
    assert report['incompatible_servo_ids']==[12,13,15,17]
    assert report['existing_pair_target_if_reused']==2916
    assert report['existing_pair_target_within_window'] is False
    assert [r['distance_outside_window_counts'] for r in report['joints']]==[0,30,28,0,444,0,5]
    assert report['base_to_board_registration']=='UNKNOWN_AFTER_REPOSITION'
    assert report['motion_authorized'] is False and report['physical_clearance_verified'] is False


def test_in_window_does_not_grant_clearance_or_authority():
    pose,hold,pair=inputs()
    for row,window in zip(pose['joints'],hold['hold_policy']['joints']):row['last_position']=window[0]
    report=compare_pose_policy(pose,hold,pair)
    assert report['incompatible_servo_ids']==[]
    assert report['existing_pair_target_within_window'] is True
    assert not report['progression_authority'] and not report['current_pose_verified']


@pytest.mark.parametrize('fault',['simulation','unstable','order','range','offset'])
def test_invalid_evidence_rejected(fault):
    pose,hold,pair=inputs()
    if fault=='simulation':pose['origin']='SIMULATION'
    if fault=='unstable':pose['category']='POSE_NOT_STABLE'
    if fault=='order':pose['joints'].reverse()
    if fault=='range':pose['joints'][0]['last_position']=5000
    if fault=='offset':pair['offset_counts']=True
    with pytest.raises(ValueError):compare_pose_policy(pose,hold,pair)


def test_replay_rejects_altered_clearance_claim(tmp_path,monkeypatch):
    from rocell.application import pose_policy_review as module
    report=dict(pose_export='pose',stage_export='stage',installation_export='install',
        physical_clearance_verified=False)
    monkeypatch.setattr(module,'build_review',lambda *a,**k:dict(report))
    monkeypatch.setattr(module,'_read',lambda *a:(dict(report),'a'*64))
    assert module.replay_review(tmp_path,'review')==report
    monkeypatch.setattr(module,'_read',lambda *a:(dict(report,physical_clearance_verified=True),'a'*64))
    with pytest.raises(ValueError,match='does not reproduce'):module.replay_review(tmp_path,'review')
