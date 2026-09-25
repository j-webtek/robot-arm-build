import math
import pytest
from rocell.arm.endpoint_quality import assess_endpoint_quality


def endpoint(error=.473,persistent=True):
    return dict(endpoint_verified=persistent,final_error_rad=math.radians(error),
        persistence=dict(status='REPORTED_ENDPOINT_PERSISTENT' if persistent else 'REPORTED_ENDPOINT_CHANGED',
                         full_window_endpoint=dict(endpoint_verified=True)))


def test_broad_pass_is_not_precision_or_next_start_pass():
    q=assess_endpoint_quality(endpoint(),final_joints=[0]*5+[.02],next_start_joints=[0]*6)
    assert q['arrival_status']=='PASSED_EXISTING_CRITERIA'
    assert q['precision_status']=='OUTSIDE_DIAGNOSTIC_SCREEN'
    assert q['next_start_status']=='REPORTED_MISMATCH'
    assert q['repeatability_status']=='NOT_ASSESSED_FROM_SINGLE_TRIAL'
    assert not q['motion_authorized'] and not q['admission_policy_changed']


def test_late_change_remains_distinct_from_small_error():
    q=assess_endpoint_quality(endpoint(.03,False),final_joints=[0]*6)
    assert q['precision_status']=='WITHIN_DIAGNOSTIC_SCREEN'
    assert q['persistence_status']=='REPORTED_ENDPOINT_CHANGED'
    assert not q['historical_endpoint_verified']
    assert q['next_start_status']=='NOT_SPECIFIED'


def test_legacy_short_capture_has_no_invented_persistence():
    q=assess_endpoint_quality(dict(endpoint_verified=True,final_error_rad=0),final_joints=[0]*6)
    assert q['persistence_status']=='NOT_ASSESSED_35S'


@pytest.mark.parametrize('error',[float('nan'),float('inf'),True,None])
def test_invalid_error_rejected(error):
    e=endpoint();e['final_error_rad']=error
    with pytest.raises(ValueError):assess_endpoint_quality(e,final_joints=[0]*6)


def test_original_not_mutated():
    e=endpoint();before=repr(e)
    assess_endpoint_quality(e,final_joints=[0]*6,next_start_joints=[0]*6)
    assert repr(e)==before
