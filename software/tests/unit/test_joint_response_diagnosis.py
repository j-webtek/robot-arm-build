import pytest
from rocell.application.joint_response_diagnosis import diagnose_joint_response


def report(final=1.5):
    return dict(status='COMPLETION_DEADLINE_EXCEEDED',run=dict(error=None,
        acknowledgment_received=True,feedback_originals=[dict(status='SUCCEEDED')],
        transaction=dict(command=dict(T=101,joint=3,rad=1.49,spd=20,acc=1),
            baseline_joints=[0,0,1.5,0,0,3],rows=[[1,2,[0,0,0,0],[0,0,final,0,0,3]]])))


@pytest.mark.parametrize('final,expected',[(1.5,'NO_REPORTED_RESPONSE'),(1.49,'SAME_DIRECTION_REPORTED_RESPONSE'),(1.51,'OPPOSITE_REPORTED_RESPONSE')])
def test_response_is_separate_from_endpoint(final,expected):
    d=diagnose_joint_response(report(final))
    assert d['classification']==expected
    assert not d['motion_authorized'] and not d['compensation_training_authorized']
    assert not d['encoder_freshness_verified']


def test_uncertain_run_cannot_be_called_no_response():
    r=report();r['run']['error']='UNCERTAIN'
    assert diagnose_joint_response(r)['classification']=='COMMAND_OR_FEEDBACK_UNCERTAIN'


def test_cross_joint_motion_not_missed():
    r=report();r['run']['transaction']['rows'][0][3][1]=.01
    assert diagnose_joint_response(r)['classification']=='OTHER_JOINT_REPORTED_CHANGE'


def test_bad_values_rejected():
    with pytest.raises(ValueError):diagnose_joint_response(report(float('nan')))
