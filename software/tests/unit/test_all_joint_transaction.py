from pathlib import Path
import pytest
from rocell.arm.all_joint_transaction import AllJointTransaction
from rocell.geometry import UrdfModel
from rocell.kinematics.firmware_reference import forward

START = [.001533981,.033747577,1.744136156,-.065961174,.018407769,3.138524692]


def feedback(q):
    return dict(status='SUCCEEDED',identity_before_matched=True,
        identity_after_matched=True,joints_rad=dict(zip(('b','s','e','t','r','g'),q)),
        controller_cartesian=dict(values=dict(zip(('x','y','z','tit'),forward(*q[:4])))))


@pytest.fixture
def tx():
    model=UrdfModel.from_file(Path(__file__).resolve().parents[3]/
        'software/models/roarm_m3/roarm_m3_kinematic_40dbd84.urdf')
    return AllJointTransaction(model,feedback(START),baseline_finished_s=1,
        overrides={'elbow':START[2]+.003,'wrist':START[3]-.003})


def settle(tx):
    tx.dispatch(1.1)
    for t in (1.5,2,2.5,3,3.5):
        tx.observe(feedback(tx.target),now_s=t)


def test_settling_and_export_required(tx):
    settle(tx)
    assert tx.state=='REPORTED_SETTLED_PENDING_EXPORT'
    assert not tx.report()['progression_ready']
    assert len(tx.rows)==5
    assert tx.rows[-1]['desired_tip_error_mm']==0
    tx.finish_export(verified=True)
    assert tx.report()['progression_ready']
    assert not tx.report()['physical_accuracy_verified']


def test_no_replay_and_command_copy(tx):
    packet=tx.dispatch(1.1);packet['elbow']=99
    assert tx.command['elbow']==tx.target[2]
    with pytest.raises(ValueError):tx.dispatch(1.2)


def test_stale_baseline_prevents_dispatch(tx):
    with pytest.raises(ValueError):tx.dispatch(2.1)
    assert tx.state=='FAULT' and tx.dispatch_s is None


@pytest.mark.parametrize('time',[1.1,2.2,float('nan')])
def test_invalid_feedback_times_fault(tx,time):
    tx.dispatch(1.1);tx.observe(feedback(tx.target),now_s=time)
    assert tx.state=='FAULT'


def test_fault_cannot_be_erased_by_later_good_endpoint(tx):
    tx.dispatch(1.1)
    bad=feedback(tx.target);bad['identity_after_matched']=False
    tx.observe(bad,now_s=1.5)
    assert tx.state=='FAULT'
    with pytest.raises(ValueError):tx.observe(feedback(tx.target),now_s=2)


def test_export_failure_stops_progression(tx):
    settle(tx);tx.finish_export(verified=False)
    assert tx.reason=='EXPORT_NOT_VERIFIED'
    assert not tx.report()['progression_ready']


def test_departure_from_endpoint_resets_dwell(tx):
    tx.dispatch(1.1)
    tx.observe(feedback(tx.target),now_s=1.5)
    tx.observe(feedback(START),now_s=2)
    assert tx.stable_since is None
    for t in (2.5,3,3.5,4):tx.observe(feedback(tx.target),now_s=t)
    assert tx.state=='OBSERVING'
    tx.observe(feedback(tx.target),now_s=4.5)
    assert tx.state=='REPORTED_SETTLED_PENDING_EXPORT'


def test_large_intermediate_excursion_fails_even_if_target_small(tx):
    tx.dispatch(1.1);q=list(START);q[2]+=.03
    tx.observe(feedback(q),now_s=1.5)
    assert tx.state=='FAULT'
    assert tx.reason=='OBSERVED_TIP_ENVELOPE_EXCEEDED'


def test_uncertain_delivery_blocks_retry(tx):
    tx.dispatch(1.1);tx.fault('UNCERTAIN_DELIVERY')
    with pytest.raises(ValueError):tx.dispatch(1.2)


def test_deadline_even_with_continuous_feedback(tx):
    tx.dispatch(1.1)
    for t in range(2,12):tx.observe(feedback(START),now_s=t)
    tx.observe(feedback(START),now_s=11.5)
    assert tx.reason=='ENDPOINT_DEADLINE'


def test_oversized_step_rejected(tx):
    with pytest.raises(ValueError):
        AllJointTransaction(tx.model,feedback(START),baseline_finished_s=1,
            overrides={'elbow':START[2]+.02})


def test_receipt_sets_first_feedback_window_but_not_completion_origin(tx):
    tx.dispatch(1.1);tx.acknowledge(1.5)
    tx.observe(feedback(tx.target),now_s=2.2)
    assert tx.state=='OBSERVING'
    assert tx.dispatch_s==1.1 and tx.receipt_s==1.5
    with pytest.raises(ValueError):tx.acknowledge(2.3)


def test_late_receipt_rejected(tx):
    tx.dispatch(1.1)
    with pytest.raises(ValueError):tx.acknowledge(2.2)
    assert tx.state=='FAULT'


def test_non_test_joint_drift_stops_without_waiting_for_deadline(tx):
    wrist_only=AllJointTransaction(tx.model,feedback(START),baseline_finished_s=1,
        overrides={'wrist':START[3]-.006})
    wrist_only.dispatch(1.1)
    q=list(START);q[2]+=.007669903
    wrist_only.observe(feedback(q),now_s=1.5)
    assert wrist_only.reason=='NON_TEST_JOINT_DRIFT'
    assert len(wrist_only.rows)==1


def test_single_joint_mode_rejects_elbow_override(tx):
    with pytest.raises(ValueError):
        AllJointTransaction(tx.model,feedback(START),baseline_finished_s=1,
            overrides={'elbow':START[2]+.003},wrist_single=True)


def test_probe_allowance_does_not_extend_t102_or_other_targets(tx):
    for single,target in [(False,-.080),(True,-.081)]:
        with pytest.raises(ValueError):
            AllJointTransaction(tx.model,feedback(START),baseline_finished_s=1,
                overrides={'wrist':target},wrist_single=single)
    changed=list(START);changed[3]-=.003
    with pytest.raises(ValueError):
        AllJointTransaction(tx.model,feedback(changed),baseline_finished_s=1,
            overrides={'wrist':-.080},wrist_single=True)


def candidate_transaction(tx):
    from rocell.application.ascending_wrist_candidate import frozen_candidate
    c=frozen_candidate()
    return AllJointTransaction(tx.model,feedback(c['baseline_joints_rad']),baseline_finished_s=1,
        overrides={'wrist':c['command']['rad']},wrist_single=True,normalized_candidate=True)


def test_wire_band_pass_cannot_substitute_for_desired_band(tx):
    c=candidate_transaction(tx);c.dispatch(1.1)
    q=list(c.target);q[3]+=.0015
    for t in (1.5,2,2.5,3,3.5):c.observe(feedback(q),now_s=t)
    assert c.rows[-1]['wire_tip_error_mm']<.5
    assert c.rows[-1]['desired_tip_error_mm']>.5
    assert c.state=='OBSERVING'


def test_candidate_desired_endpoint_is_scored_and_exported(tx):
    c=candidate_transaction(tx);c.dispatch(1.1)
    for t in (1.5,2,2.5,3,3.5):c.observe(feedback(c.desired),now_s=t)
    assert c.state=='REPORTED_SETTLED_PENDING_EXPORT'
    assert c.rows[-1]['desired_tip_error_mm']==0
    assert c.rows[-1]['wire_tip_error_mm']>0
    assert c.report()['compensation_applied']
    assert c.report()['candidate']['source_sha256']


def test_elbow_compensation_requires_desired_not_wire_endpoint(tx):
    from rocell.application.local_elbow_bias_candidate import frozen_candidate
    candidate=frozen_candidate()
    c=AllJointTransaction(tx.model,feedback(candidate['baseline_joints_rad']),
        baseline_finished_s=1,overrides={'elbow':candidate['command']['rad']},
        normalized_candidate='elbow')
    c.dispatch(1.1)
    # Settled at the transmitted angle alone is not successful compensation.
    for t in (1.5,2,2.5,3,3.5):c.observe(feedback(c.target),now_s=t)
    assert c.rows[-1]['wire_tip_error_mm']==0
    assert c.rows[-1]['desired_tip_error_mm']>.5
    assert c.state=='OBSERVING'
    for t in (4,4.5,5,5.5,6):c.observe(feedback(c.desired),now_s=t)
    assert c.state=='REPORTED_SETTLED_PENDING_EXPORT'
    assert c.rows[-1]['desired_tip_error_mm']==0
