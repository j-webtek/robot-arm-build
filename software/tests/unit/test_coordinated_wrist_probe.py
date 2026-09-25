import pytest
from test_compensated_elbow_native import baseline
from rocell.kinematics.firmware_reference import forward
from rocell.application.coordinated_wrist_probe import preview_wrist_probe
from rocell.arm.cartesian_transaction import CartesianTransaction


def posture():
    b=baseline(1.563126423); b['joints_rad'].update(s=.007669904,t=.03834952)
    b['controller_cartesian']['values']=dict(zip(('x','y','z','tit'),forward(*(b['joints_rad'][k] for k in ('b','s','e','t')))))
    return b


def test_wrist_only_mapping_and_scoring():
    b=posture(); p=preview_wrist_probe(b)
    tx=CartesianTransaction(baseline=b,baseline_finished_ns=1,completion_budget_ns=3_000_000_000,wrist_probe=True)
    command=tx.begin_dispatch(2);tx.acknowledge(3)
    assert command['T']==101 and command['joint']==4
    assert command['spd']==20 and command['acc']==1
    for i in range(1,5):
        end=i*250_000_000
        tx.observe((end-1,end,p['target_pose'],p['target_joints_rad']),end)
    result=tx.snapshot()
    assert result['state']=='REPORTED_ENDPOINT_VERIFIED'
    assert [r['joint'] for r in result['result']['joint_comparison'] if r['commanded']]==['t']
    with pytest.raises(ValueError):tx.begin_dispatch(2_000_000_000)


def test_wrong_posture_and_mixed_modes_rejected():
    with pytest.raises(ValueError):preview_wrist_probe(baseline())
    with pytest.raises(ValueError):CartesianTransaction(baseline=posture(),baseline_finished_ns=1,
        completion_budget_ns=3_000_000_000,wrist_probe=True,ghost_first_step=True)


def test_candidate_scores_wrist_not_elbow_and_keeps_wire_miss():
    b=posture(); b['joints_rad']['t']=.026077673
    b['controller_cartesian']['values']=dict(zip(('x','y','z','tit'),forward(*(b['joints_rad'][k] for k in ('b','s','e','t')))))
    tx=CartesianTransaction(baseline=b,baseline_finished_ns=1,completion_budget_ns=3_000_000_000,wrist_probe=True,wrist_candidate=True)
    command=tx.begin_dispatch(2);tx.acknowledge(3)
    assert command['rad']==pytest.approx(-.003908091779914946)
    desired=list(b['joints_rad'].values()); desired[3]=.010
    for i in range(1,5):
        end=i*250_000_000
        tx.observe((end-1,end,forward(*desired[:4]),desired),end)
    result=tx.snapshot()
    assert not result['result']['endpoint_verified']
    assert result['desired_endpoint_result']['status']=='DESIRED_REPORTED_ENDPOINT_VERIFIED'
    assert result['desired_endpoint_result']['wrist_error_deg']==0
    assert 'elbow_error_deg' not in result['desired_endpoint_result']


def test_preparation_is_separate_and_preserves_other_joints():
    b=posture(); b['joints_rad']['t']=.007669904
    b['controller_cartesian']['values']=dict(zip(('x','y','z','tit'),forward(*(b['joints_rad'][k] for k in ('b','s','e','t')))))
    p=preview_wrist_probe(b,prepare=True)
    assert p['target_joints_rad'][3]==.026077673 and p['local_candidate'] is None
    assert all(v==p['target_joints_rad'][i] for i,v in enumerate(b['joints_rad'].values()) if i!=3)
    with pytest.raises(ValueError):preview_wrist_probe(b,candidate=True,prepare=True)
    with pytest.raises(ValueError):preview_wrist_probe(posture(),prepare=True)


def test_extended_start_preserves_fit_and_original_identity():
    from rocell.application.coordinated_wrist_probe import wrist_candidate_record
    original=wrist_candidate_record(); extended=wrist_candidate_record(extended_start=True)
    assert original['candidate_sha256']=='24b4bb51d8e27ff3bd36e1d960134f879264e9aba1801d1967ba7f14f10e0583'
    assert extended['parent_candidate_sha256']==original['candidate_sha256']
    assert extended['command_rad']==original['command_rad']
    for value in (.017999,.018,.01994175,.027,.027001):
        b=posture(); b['joints_rad']['t']=value
        b['controller_cartesian']['values']=dict(zip(('x','y','z','tit'),forward(*(b['joints_rad'][k] for k in ('b','s','e','t')))))
        if .018<=value<=.027:
            p=preview_wrist_probe(b,candidate='extended-start')
            assert p['target_joints_rad'][3]==original['command_rad']
            assert len(p['samples'])==41
        else:
            with pytest.raises(ValueError):preview_wrist_probe(b,candidate='extended-start')


def test_post_coordinated_diagnostic_is_separate_and_bounded():
    b=posture();b['joints_rad'].update(s=.033747577,e=1.636757501,t=-.065961174,r=.018407769)
    b['controller_cartesian']['values']=dict(zip(('x','y','z','tit'),forward(*(b['joints_rad'][k] for k in ('b','s','e','t')))))
    p=preview_wrist_probe(b,post_coordinated=True)
    tx=CartesianTransaction(baseline=b,baseline_finished_ns=1,completion_budget_ns=3_000_000_000,
        wrist_probe='post-coordinated')
    command=tx.begin_dispatch(2);tx.acknowledge(3)
    assert command['joint']==4 and command['T']==101 and command['spd']==20 and command['acc']==1
    assert p['local_candidate'] is None
    for i in range(1,5):
        end=i*250_000_000
        tx.observe((end-1,end,p['target_pose'],p['target_joints_rad']),end)
    assert tx.snapshot()['state']=='REPORTED_ENDPOINT_VERIFIED'
    with pytest.raises(ValueError):preview_wrist_probe(b)
    with pytest.raises(ValueError):preview_wrist_probe(b,post_coordinated=True,candidate=True)


def test_ascending_scope_has_no_descending_compensation():
    import math
    b=posture();b['joints_rad'].update(s=.033747577,e=1.636757501,t=-.093572828,r=.018407769)
    b['controller_cartesian']['values']=dict(zip(('x','y','z','tit'),forward(*(b['joints_rad'][k] for k in ('b','s','e','t')))))
    p=preview_wrist_probe(b,post_coordinated=True,ascending=True)
    assert p['target_joints_rad'][3]==pytest.approx(-.093572828+math.radians(1.5))
    assert p['local_candidate'] is None
    tx=CartesianTransaction(baseline=b,baseline_finished_ns=1,completion_budget_ns=3_000_000_000,
        wrist_probe='post-coordinated-ascending')
    assert tx.begin_dispatch(2)['rad']==p['target_joints_rad'][3]
    with pytest.raises(ValueError):preview_wrist_probe(b,post_coordinated=True,ascending=True,candidate=True)
    with pytest.raises(ValueError):preview_wrist_probe(b,post_coordinated=True)


def test_ascending_candidate_has_own_bias_and_clean_desired_completion():
    from rocell.application.coordinated_wrist_probe import wrist_candidate_record
    b=posture();b['joints_rad'].update(s=.033747577,e=1.636757501,t=-.072097097,r=.018407769)
    b['controller_cartesian']['values']=dict(zip(('x','y','z','tit'),forward(*(b['joints_rad'][k] for k in ('b','s','e','t')))))
    c=wrist_candidate_record(post_coordinated=True,ascending=True)
    assert c['training_residual_rad']<0 and c['command_rad']>c['desired_rad']
    tx=CartesianTransaction(baseline=b,baseline_finished_ns=1,completion_budget_ns=3_000_000_000,
        wrist_probe='post-coordinated-ascending',wrist_candidate=True,compensated_endpoint=True)
    assert tx.begin_dispatch(2)['rad']==c['command_rad'];tx.acknowledge(3)
    joints=list(b['joints_rad'].values());joints[3]=c['desired_rad']
    for i in range(1,5):
        end=i*250_000_000;tx.observe((end-1,end,forward(*joints[:4]),joints),end)
    assert tx.snapshot()['state']=='COMPENSATED_REPORTED_ENDPOINT_VERIFIED'
    assert tx.snapshot()['policy']['scope']=='POST_COORDINATED_WRIST_ASCENDING_CANDIDATE_V1'
    assert not tx.snapshot()['result']['endpoint_verified']


@pytest.mark.parametrize('nearby',[False,True])
def test_post_coordinated_candidate_holds_other_joints_and_scores_desired(nearby):
    from rocell.application.coordinated_wrist_probe import wrist_candidate_record
    b=posture();b['joints_rad'].update(s=.033747577,e=1.636757501,t=-.084368943 if nearby else -.075165059,r=.018407769)
    b['controller_cartesian']['values']=dict(zip(('x','y','z','tit'),forward(*(b['joints_rad'][k] for k in ('b','s','e','t')))))
    candidate='nearby-target' if nearby else True
    c=wrist_candidate_record(post_coordinated=True,nearby=nearby)
    p=preview_wrist_probe(b,post_coordinated=True,candidate=candidate)
    assert c['desired_rad']==(-.094203884 if nearby else -.085) and c['command_rad']<c['desired_rad']
    assert c['training_residual_rad']==wrist_candidate_record(post_coordinated=True)['training_residual_rad']
    assert p['local_candidate']==c
    tx=CartesianTransaction(baseline=b,baseline_finished_ns=1,completion_budget_ns=3_000_000_000,
        wrist_probe='post-coordinated',wrist_candidate=candidate,compensated_endpoint=True)
    assert tx.begin_dispatch(2)['rad']==c['command_rad'];tx.acknowledge(3)
    joints=list(b['joints_rad'].values());joints[3]=c['desired_rad']
    for i in range(1,5):
        end=i*250_000_000;tx.observe((end-1,end,forward(*joints[:4]),joints),end)
    assert tx.snapshot()['state']=='COMPENSATED_REPORTED_ENDPOINT_VERIFIED'
    assert not tx.snapshot()['result']['endpoint_verified']
    with pytest.raises(ValueError):preview_wrist_probe(b,post_coordinated=True,candidate='extended-start')
