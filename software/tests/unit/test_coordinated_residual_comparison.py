import pytest
from test_coordinated_candidate import source
from rocell.application.coordinated_residual_comparison import compare_coordinated_residuals


def test_changed_start_is_not_repeatability_and_error_is_retained():
    first=source();second=source()
    second['run']['transaction']['baseline_joints'][2]+=.01
    second['run']['transaction']['expected_joints'][2]-=.003
    second['run']['error']='TRANSACTION_INTERRUPTED_OR_UNCERTAIN'
    r=compare_coordinated_residuals([first,second])
    assert not r['same_start'] and not r['repeatability_established']
    assert not r['correction_qualified'] and not r['motion_authorized']
    assert r['joints'][2]['residual_change_rad']==pytest.approx(.003)
    assert r['source_outcomes'][1]['runner_error']=='TRANSACTION_INTERRUPTED_OR_UNCERTAIN'


def test_invalid_feedback_is_not_used():
    r=source();r['run']['transaction']['rows'][-1][2][0]+=1
    with pytest.raises(ValueError):compare_coordinated_residuals([source(),r])
