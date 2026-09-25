import pytest
from rocell.application import post_tip_wrist_candidate as module


@pytest.fixture
def evidence(monkeypatch):
    start=[.001533981,.033747577,1.67357304,-.052155347,.018407769,3.138524692]
    final=list(start);final[3]=-.064427193
    review=dict(feedback_failures=[],joints=[{}, {}, {},dict(
        requested_delta_deg=-1.5,reported_delta_deg=-.703125,unchanged_tail_s=8)])
    monkeypatch.setattr(module,'review_coordinated_trace',lambda report:review)
    report=dict(run=dict(error=None,acknowledgment_received=True,transaction=dict(
        policy=dict(scope='POST_TIP_WRIST_RESPONSE_MINUS_1P5_DEGREES_V1'),
        command=dict(T=101,joint=4,rad=-.07833528577991494,spd=20,acc=1),
        baseline_joints=start,rows=[[1,2,None,final]])))
    return report,review


def test_distinct_target_and_fixed_local_correction(evidence):
    report,_=evidence;c=module.build_candidate(report)
    assert c['desired_rad']==-.075
    assert c['command_rad']==pytest.approx(-.08890809277991495)
    assert c['hypothetical_tip_sweep_mm']<6
    assert not c['held_out_validated'] and not c['motion_authorized']
    assert c==module.build_candidate(report)


def test_posture_transfer_preserves_correction_and_recomputes_geometry(evidence):
    parent=module.build_candidate(evidence[0])
    c=module.transfer_post_overshoot_candidate(parent)
    assert c['parent_candidate_sha256']==parent['candidate_sha256']
    for key in ('desired_rad','command_rad','training_residual_rad','training_export','spd','acc'):
        assert c[key]==parent[key]
    assert parent['baseline_joints_rad'][2]==1.67357304
    assert c['baseline_joints_rad'][2]==1.691980809
    assert c['wire_pose']!=parent['wire_pose']
    assert c['candidate_sha256']!=parent['candidate_sha256']
    assert c['hypothetical_tip_sweep_mm']<6
    assert not c['held_out_validated'] and not c['motion_authorized']
    parent['command_rad']+=.001
    with pytest.raises(ValueError):module.transfer_post_overshoot_candidate(parent)


def test_transferred_candidate_transaction_checks_desired_endpoint(evidence,monkeypatch):
    from test_post_tip_wrist import post_overshoot_source
    from rocell.application import product_ghost_export_review
    from rocell.arm.cartesian_transaction import CartesianTransaction
    from rocell.kinematics.firmware_reference import forward
    parent=module.build_candidate(evidence[0]);c=module.transfer_post_overshoot_candidate(parent)
    monkeypatch.setattr(product_ghost_export_review,'_read',lambda *args:(parent,'digest'))
    b=post_overshoot_source();b['joints_rad']['t']=c['baseline_joints_rad'][3]
    b['controller_cartesian']['values']=dict(zip(('x','y','z','tit'),forward(*c['baseline_joints_rad'][:4])))
    tx=CartesianTransaction(baseline=b,baseline_finished_ns=1,completion_budget_ns=3_000_000_000,
        wrist_probe='post-overshoot-candidate',wrist_candidate=True,compensated_endpoint=True)
    assert tx.begin_dispatch(2)['rad']==parent['command_rad']
    tx.acknowledge(3)
    for i in range(1,5):
        end=i*250_000_000
        tx.observe((end-1,end,c['desired_pose'],c['desired_joints_rad']),end)
    assert tx.snapshot()['state']=='COMPENSATED_REPORTED_ENDPOINT_VERIFIED'
    assert tx.snapshot()['observed_hypothetical_tip_displacement_mm']<6
    with pytest.raises(ValueError):module.preview_frozen_candidate(b)


@pytest.mark.parametrize('fault',['error','ack','direction','settling','other_joint','command'])
def test_uninterpretable_training_rejected(evidence,fault):
    report,review=evidence;run=report['run'];tx=run['transaction']
    if fault=='error':run['error']='UNCERTAIN'
    if fault=='ack':run['acknowledgment_received']=False
    if fault=='direction':review['joints'][3]['reported_delta_deg']=0
    if fault=='settling':review['joints'][3]['unchanged_tail_s']=.1
    if fault=='other_joint':tx['rows'][-1][3][2]+=.01
    if fault=='command':tx['command']['spd']=30
    with pytest.raises(ValueError):module.build_candidate(report)


def test_held_out_verifies_desired_not_wire(evidence,monkeypatch):
    from test_post_tip_elbow import source
    from rocell.application import product_ghost_export_review
    from rocell.arm.cartesian_transaction import CartesianTransaction
    from rocell.kinematics.firmware_reference import forward
    c=module.build_candidate(evidence[0])
    monkeypatch.setattr(product_ghost_export_review,'_read',lambda *args:(c,'digest'))
    b=source();b['joints_rad']['t']=c['baseline_joints_rad'][3]
    b['controller_cartesian']['values']=dict(zip(('x','y','z','tit'),forward(*c['baseline_joints_rad'][:4])))
    tx=CartesianTransaction(baseline=b,baseline_finished_ns=1,completion_budget_ns=3_000_000_000,
        wrist_probe='post-tip-candidate',wrist_candidate=True,compensated_endpoint=True)
    assert tx.begin_dispatch(2)['rad']==c['command_rad']
    tx.acknowledge(3)
    for i in range(1,5):
        end=i*250_000_000
        tx.observe((end-1,end,c['desired_pose'],c['desired_joints_rad']),end)
    snap=tx.snapshot()
    assert snap['desired_endpoint_result']['status']=='DESIRED_REPORTED_ENDPOINT_VERIFIED'
    assert not snap['result']['endpoint_verified']
    assert snap['state']=='COMPENSATED_REPORTED_ENDPOINT_VERIFIED'
    c['command_rad']+=.001
    with pytest.raises(ValueError,match='changed'):module.preview_frozen_candidate(b)


def test_reverse_candidate_is_distinct_and_direction_specific(evidence):
    report,review=evidence;tx=report['run']['transaction']
    tx['policy']['scope']='POST_TIP_WRIST_RESPONSE_PLUS_1P5_DEGREES_V1'
    tx['command']['rad']=-.045917158220085054
    tx['baseline_joints'][3]=-.072097097
    tx['rows'][-1][3][3]=-.052155347
    review['joints'][3].update(requested_delta_deg=1.5,reported_delta_deg=1.142578111)
    c=module.build_candidate(report,reverse=True)
    assert c['desired_rad']==-.060
    assert c['command_rad']==pytest.approx(-.053761811220085054)
    assert c['hypothetical_tip_sweep_mm']<6
    assert c['candidate_sha256']=='376e3e9352a23da6e447d2d4850ff7411a9d5fdffe9d7c7125661bdbfdea8dbf'
    with pytest.raises(ValueError):module.build_candidate(report)
