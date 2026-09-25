import math
import pytest
from rocell.application.coordinated_candidate import preview_coordinated_candidate, frozen_candidate, preview_frozen_candidate
from rocell.kinematics.firmware_reference import forward
from rocell.arm.cartesian_transaction import CartesianTransaction
from test_compensated_elbow_native import baseline


def candidate_baseline():
    b=baseline();c=frozen_candidate()
    b['joints_rad']=dict(zip(('b','s','e','t','r','g'),c['baseline_joints_rad']))
    b['controller_cartesian']['values']=dict(zip(('x','y','z','tit'),forward(*c['baseline_joints_rad'][:4])))
    return b


def test_frozen_candidate_identity_and_desired_completion():
    c=frozen_candidate();b=candidate_baseline();p=preview_frozen_candidate(b)
    assert c['candidate_sha256']=='2745b882dd25f533a58d6739ab5580486f78d79ad834fabfec2736c6fbf1aa83'
    assert p['target_pose']==c['wire_pose']
    tx=CartesianTransaction(baseline=b,baseline_finished_ns=1,completion_budget_ns=3_000_000_000,
        ghost_first_step='coordinated-candidate',compensated_endpoint=True)
    command=tx.begin_dispatch(2);tx.acknowledge(3)
    assert command['T']==104 and command['z']==c['wire_pose'][2]
    for i in range(1,5):
        end=i*250_000_000
        tx.observe((end-1,end,c['desired_pose'],c['desired_joints_rad']),end)
    result=tx.snapshot()
    assert result['state']=='COMPENSATED_REPORTED_ENDPOINT_VERIFIED'
    assert not result['result']['endpoint_verified']
    assert result['desired_endpoint_result']['position_error_mm']<1e-6
    assert len(result['desired_endpoint_result']['joint_errors_deg'])==6


@pytest.mark.parametrize('fault',['gap','incoherent','drift'])
def test_frozen_candidate_faults_override_desired_scoring(fault):
    c=frozen_candidate();tx=CartesianTransaction(baseline=candidate_baseline(),baseline_finished_ns=1,
        completion_budget_ns=3_000_000_000,ghost_first_step='coordinated-candidate',compensated_endpoint=True)
    tx.begin_dispatch(2);tx.acknowledge(3)
    pose=c['desired_pose'][:];joints=c['desired_joints_rad'][:];end=250_000_000
    if fault=='gap':end=1_500_000_000
    if fault=='incoherent':pose[0]+=1
    if fault=='drift':joints[4]+=.1
    tx.observe((end-1,end,pose,joints),end)
    assert tx.snapshot()['state'] in ('FEEDBACK_GAP_EXCEEDED','CONTROLLER_MODEL_MISMATCH','UNEXPECTED_JOINT_CHANGE')


def test_frozen_candidate_rejects_different_posture():
    b=candidate_baseline();b['joints_rad']['e']+=.001
    with pytest.raises(ValueError):preview_frozen_candidate(b)


def test_affine_joint_timing_skew_stops_on_intermediate_tip_excursion():
    c=frozen_candidate(tip=True,post_transfer=True,affine=True);b=baseline()
    q=list(c['baseline_joints_rad'])
    b['joints_rad']=dict(zip(('b','s','e','t','r','g'),q))
    b['controller_cartesian']['values']=dict(zip(('x','y','z','tit'),forward(*q[:4])))
    tx=CartesianTransaction(baseline=b,baseline_finished_ns=1,completion_budget_ns=3_000_000_000,
        ghost_first_step='affine-interior',compensated_endpoint=True)
    tx.begin_dispatch(2);tx.acknowledge(3)
    # Retained fault sample: elbow response precedes any reported wrist change.
    # A later desired endpoint would not erase this observed envelope violation.
    q[2]=1.744136156
    tx.observe((100_000_000,200_000_000,forward(*q[:4]),q),200_000_000)
    assert tx.snapshot()['state']=='OBSERVED_HYPOTHETICAL_TIP_BOUND_EXCEEDED'
    assert tx.snapshot()['observed_hypothetical_tip_displacement_mm']>6
    with pytest.raises(ValueError):
        tx.observe((300_000_000,400_000_000,c['desired_pose'],c['desired_joints_rad']),400_000_000)


@pytest.mark.parametrize('affine',[False,True])
def test_post_transfer_frozen_command_and_desired_endpoint(affine):
    c=frozen_candidate(tip=True,post_transfer=True,affine=affine);b=baseline()
    b['joints_rad']=dict(zip(('b','s','e','t','r','g'),c['baseline_joints_rad']))
    b['controller_cartesian']['values']=dict(zip(('x','y','z','tit'),forward(*c['baseline_joints_rad'][:4])))
    p=preview_frozen_candidate(b,tip=True,post_transfer=True,affine=affine)
    assert p['local_candidate']['candidate_sha256']==('c322d3db96a664f86cab305180ba99917154aa4d9c7df75dabcd6da13e121075' if affine else '563d49058fd7497f46b7441434981e8bc27ae1538055d99cfdb443b7ee4ebd56')
    mode='affine-interior' if affine else 'post-transfer-candidate'
    tx=CartesianTransaction(baseline=b,baseline_finished_ns=1,completion_budget_ns=3_000_000_000,
        ghost_first_step=mode,compensated_endpoint=True)
    assert tx.begin_dispatch(2)['z']==c['wire_pose'][2]
    tx.acknowledge(3)
    for i in range(1,5):
        end=i*250_000_000;tx.observe((end-1,end,c['desired_pose'],c['desired_joints_rad']),end)
    assert tx.snapshot()['state']=='COMPENSATED_REPORTED_ENDPOINT_VERIFIED'
    assert tx.snapshot()['observed_hypothetical_tip_displacement_mm']<6
    assert tx.snapshot()['policy']['scope']==('COORDINATED_AFFINE_INTERIOR_V1' if affine else 'POST_TRANSFER_TIP_HELD_OUT_V1')
    with pytest.raises(ValueError):preview_frozen_candidate(b,tip=True)
    with pytest.raises(ValueError):
        CartesianTransaction(baseline=b,baseline_finished_ns=1,completion_budget_ns=3_000_000_000,
            ghost_first_step=mode)


def test_v2_is_separate_and_preserves_v1_and_source_failure():
    c=frozen_candidate(revised=True)
    assert c['parent_candidate_sha256']==frozen_candidate()['candidate_sha256']
    assert c['training_runner_error']=='TRANSACTION_INTERRUPTED_OR_UNCERTAIN'
    b=candidate_baseline()
    with pytest.raises(ValueError):preview_frozen_candidate(b,revised=True)
    b['joints_rad']=dict(zip(('b','s','e','t','r','g'),c['baseline_joints_rad']))
    b['controller_cartesian']['values']=dict(zip(('x','y','z','tit'),forward(*c['baseline_joints_rad'][:4])))
    p=preview_frozen_candidate(b,revised=True)
    assert p['local_candidate']==c
    tx=CartesianTransaction(baseline=b,baseline_finished_ns=1,completion_budget_ns=3_000_000_000,
        ghost_first_step='coordinated-candidate-v2',compensated_endpoint=True)
    assert tx.snapshot()['policy']['scope']=='COORDINATED_OFFSET_HELD_OUT_V2'
    tx.begin_dispatch(2);tx.acknowledge(3)
    for i in range(1,5):
        end=i*250_000_000
        tx.observe((end-1,end,c['desired_pose'],c['desired_joints_rad']),end)
    assert tx.snapshot()['state']=='COMPENSATED_REPORTED_ENDPOINT_VERIFIED'


def source():
    start=[.001533981,.007669904,1.563126423,.007669904,.018407769,3.138524692]
    expected=[.000331804149,.016033979116,1.584945299528,-.022717952251,*start[4:]]
    final=[.001533981,.015339808,1.590738077,-.010737866,*start[4:]]
    rows=[[i*500_000_000,i*500_000_000+1,list(forward(*final[:4])),final[:]] for i in range(1,7)]
    tx=dict(command=dict(T=104,spd=.05),baseline_joints=start,expected_joints=expected,
        dispatch_started_ns=1,rows=rows,policy=dict(scope='POST_WRIST_GHOST_APPROACH_5MM_UNCOMPENSATED_V2'))
    return dict(schema='rocell.native_cartesian_trial.v1',status='COMPLETION_DEADLINE_EXCEEDED',
        run=dict(transaction=tx,error=None,acknowledgment_received=True,feedback_originals=[]))


def test_candidate_separates_desired_wire_and_evidence():
    report=source();p=preview_coordinated_candidate(report);c=p['candidate']
    assert not p['motion_authorized'] and p['held_out_validation_required']
    assert c['corrected_joint_indices']==[2,3]
    assert c['residual_rad'][2]==pytest.approx(.005792777472)
    assert c['residual_rad'][3]==pytest.approx(.011980086251)
    assert p['maximum_reference_sweep_mm']<=10 and p['maximum_joint_excursion_deg']<=3
    assert math.dist(forward(*c['baseline_joints_rad'][:4])[:3],c['desired_pose'][:3])==pytest.approx(5)
    assert c['wire_joints_rad'][4:]==c['baseline_joints_rad'][4:]
    assert preview_coordinated_candidate(report)==p


@pytest.mark.parametrize('fault',['receipt','error','short','scope','feedback','direction','opposite_response','nan','roll'])
def test_bad_mapping_evidence_rejected(fault):
    r=source();tx=r['run']['transaction']
    if fault=='receipt':r['run']['acknowledgment_received']=False
    if fault=='error':r['run']['error']='TRANSACTION_INTERRUPTED_OR_UNCERTAIN'
    if fault=='short':tx['rows']=tx['rows'][:2]
    if fault=='scope':tx['policy']['scope']='OTHER'
    if fault=='feedback':r['run']['feedback_originals']=[dict(status='TIMEOUT')]
    if fault=='direction':tx['baseline_joints'][2]=1.6
    if fault=='opposite_response':
        for row in tx['rows']:
            row[3][2]=tx['baseline_joints'][2]-.003
            row[2]=list(forward(*row[3][:4]))
    if fault=='nan':tx['expected_joints'][2]=float('nan')
    if fault=='roll':tx['baseline_joints'][4]+=.01
    with pytest.raises(ValueError):preview_coordinated_candidate(r)


def tip_source():
    from rocell.application.local_tip_press import START,GOAL
    r=source();tx=r['run']['transaction']
    tx['baseline_joints']=list(START)
    tx['expected_joints']=[*GOAL,*START[4:]]
    final=[.001533981,.033747577,1.65516527,-.053689328,*START[4:]]
    tx['rows']=[[i*500_000_000,i*500_000_000+1,list(forward(*final[:4])),final[:]] for i in range(1,7)]
    tx['policy']['scope']='LOCAL_HYPOTHETICAL_TIP_PRESS_2MM_V1'
    return r


def tip_model():
    from pathlib import Path
    from rocell.geometry import UrdfModel
    return UrdfModel.from_file(Path(__file__).resolve().parents[3]/'software/models/roarm_m3/roarm_m3_kinematic_40dbd84.urdf')


def test_tip_candidate_is_distinct_held_out_goal_and_keeps_roll_gripper():
    r=tip_source();p=preview_coordinated_candidate(r,tip_model=tip_model());c=p['candidate']
    assert c['experiment']=='LOCAL_TIP_PRESS_HELD_OUT_V1'
    assert c['baseline_joints_rad']==r['run']['transaction']['rows'][-1][3]
    assert c['desired_joints_rad']!=r['run']['transaction']['expected_joints']
    assert c['wire_joints_rad'][4:]==c['baseline_joints_rad'][4:]
    assert p['maximum_hypothetical_wire_tip_sweep_mm']<10
    assert c['wire_joints_rad'][2]>c['baseline_joints_rad'][2]
    assert c['wire_joints_rad'][3]<c['baseline_joints_rad'][3]
    assert not p['motion_authorized'] and p['held_out_validation_required']


def test_post_transfer_candidate_is_separate_and_keeps_six_mm_bound():
    r=tip_source();tx=r['run']['transaction']
    tx['policy']['scope']='POST_TRANSFER_TIP_PRESS_2MM_V1'
    tx['baseline_joints'][2]=1.691980809
    tx['expected_joints']=[.0015339803420119486,.03509433335332164,1.7042865196488426,-.06580586570901861,.018407769,3.138524692]
    for row in tx['rows']:
        row[3][2]=1.710388578;row[2]=list(forward(*row[3][:4]))
    p=preview_coordinated_candidate(r,tip_model=tip_model(),post_transfer=True)
    c=p['candidate']
    assert c['experiment']=='POST_TRANSFER_TIP_HELD_OUT_V1'
    assert p['maximum_hypothetical_wire_tip_sweep_mm']<6
    assert not c['held_out_validated'] and not c['repeatability_verified']
    assert c['residual_rad'][2]==pytest.approx(.006102058351157513)
    with pytest.raises(ValueError):preview_coordinated_candidate(r,tip_model=tip_model())
    with pytest.raises(ValueError):preview_coordinated_candidate(r,post_transfer=True)


@pytest.mark.parametrize('fault',['scope','error','settling'])
def test_tip_candidate_rejects_invalid_source(fault):
    r=tip_source()
    if fault=='scope':r['run']['transaction']['policy']['scope']='OTHER'
    if fault=='error':r['run']['error']='UNCERTAIN'
    if fault=='settling':r['run']['transaction']['rows']=r['run']['transaction']['rows'][:2]
    with pytest.raises(ValueError):preview_coordinated_candidate(r,tip_model=tip_model())


def test_pinned_tip_artifact_binds_command_and_desired_endpoint():
    c=frozen_candidate(tip=True);b=baseline()
    b['joints_rad']=dict(zip(('b','s','e','t','r','g'),c['baseline_joints_rad']))
    b['controller_cartesian']['values']=dict(zip(('x','y','z','tit'),forward(*c['baseline_joints_rad'][:4])))
    p=preview_frozen_candidate(b,tip=True)
    assert p['local_candidate']==c
    tx=CartesianTransaction(baseline=b,baseline_finished_ns=1,completion_budget_ns=3_000_000_000,
        ghost_first_step='local-tip-candidate',compensated_endpoint=True)
    assert tx.snapshot()['local_candidate']['candidate_sha256']==c['candidate_sha256']
    cmd=tx.begin_dispatch(2);tx.acknowledge(3)
    assert cmd['z']==c['wire_pose'][2] and cmd['z']!=c['desired_pose'][2]
    for i in range(1,5):
        end=i*250_000_000
        tx.observe((end-1,end,c['desired_pose'],c['desired_joints_rad']),end)
    assert tx.snapshot()['state']=='COMPENSATED_REPORTED_ENDPOINT_VERIFIED'
    assert not tx.snapshot()['result']['endpoint_verified']
    assert tx.snapshot()['policy']['scope']=='LOCAL_TIP_PRESS_HELD_OUT_V1'
    b['joints_rad']['e']+=.001
    with pytest.raises(ValueError):preview_frozen_candidate(b,tip=True)


def test_pinned_tip_artifact_rejects_tampering(monkeypatch):
    from rocell.application import product_ghost_export_review
    c=frozen_candidate(tip=True);c['wire_pose'][2]+=.1
    monkeypatch.setattr(product_ghost_export_review,'_read',lambda *args:({'candidate':c},'unused'))
    with pytest.raises(ValueError,match='changed'):frozen_candidate(tip=True)
