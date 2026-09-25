import pytest
from rocell.application.joint_diagnostic_assessment import assess_joint_run


def run(state='FAULT',reason='FEEDBACK_OR_COMPLETION_WINDOW_EXHAUSTED',attempted=True,receipt=True):
    return dict(command_send_attempted=attempted,acknowledgment_received=receipt,
        transaction=dict(state=state,reason=reason,
            baseline=dict(joints_rad=dict.fromkeys(('b','s','e','t','r','g'),0.)),
            rows=[dict(reported_joints_rad=[0.]*6)]))


@pytest.mark.parametrize('attempted,receipt,category',[
    (False,False,'NO_SEND_ATTEMPT_RECORDED'),
    (True,False,'COMMAND_DELIVERY_UNCERTAIN'),
    (True,True,'REPORTED_ENDPOINT_NOT_VERIFIED')])
def test_receipt_is_not_servo_acceptance(attempted,receipt,category):
    result=assess_joint_run(run(attempted=attempted,receipt=receipt))
    assert result['category']==category
    assert result['servo_target_acceptance']=='UNAVAILABLE'
    assert not result['progression_authority']


def test_stationary_does_not_mean_stale_or_mechanical_failure():
    result=assess_joint_run(run())
    assert result['reported_positions_unchanged'] is True
    assert result['encoder_acquisition_freshness']=='UNAVAILABLE'
    assert result['physical_cause']=='UNDETERMINED'


def test_invalid_observation_not_reported_as_normal_nonarrival():
    result=assess_joint_run(run(reason='TRANSACTION_INTERRUPTED_OR_UNCERTAIN'))
    assert result['category']=='OBSERVATION_OR_EXECUTION_UNCERTAIN'


def test_endpoint_pass_is_not_physical_accuracy_or_export_pass():
    result=assess_joint_run(run(state='REPORTED_SETTLED_PENDING_EXPORT',reason=None))
    assert result['category']=='REPORTED_ENDPOINT_CRITERIA_MET'
    assert result['export_verification']=='SEPARATE_VERIFIER_REQUIRED'
    assert not result['physical_accuracy_verified']


def test_absent_feedback_is_not_stationary():
    report=run();report['transaction']['rows']=[]
    result=assess_joint_run(report)
    assert result['category']=='NO_USABLE_POST_COMMAND_OBSERVATION'
    assert result['reported_positions_unchanged'] is None
