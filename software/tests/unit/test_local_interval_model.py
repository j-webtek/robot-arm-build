import pytest

from rocell.application.local_interval_campaign import ROUTE
from rocell.application.local_interval_model import fit_local_interval


def session(actuals):
    sample_iter=iter(actuals);rows=[]
    sample_legs={0,1,4,7,10}
    for leg,command in enumerate(ROUTE):
        actual=next(sample_iter) if leg in sample_legs else [2385,1730]
        rows.append({'leg':leg,'target':[command,4114-command],'actual':actual})
    return rows


def evidence():
    values=[[2385,1730],[2386,1729],[2387,1728],[2389,1725],[2391,1724]]
    return [session(values) for _ in range(3)]


def test_piecewise_fit_releases_only_bounded_interval():
    model=fit_local_interval(evidence(),source_exports=['a','b','c'])
    assert model['local_interval_interpolation_validated'] is True
    assert model['heldout_maximum_paired_error_counts']<=2
    assert model['domain']=={'minimum_command':2377,'maximum_command':2389,
                             'extrapolation_allowed':False}
    assert model['movement_authorized'] is False


def test_smaller_upper_interval_is_classified_independently():
    sessions=evidence()
    lower_samples=([2385,1731],[2385,1730],[2386,1730])
    for rows,actual in zip(sessions,lower_samples):
        rows[1]['actual']=list(actual)
    model=fit_local_interval(sessions,source_exports=['a','b','c'])
    assert model['local_interval_interpolation_validated'] is False
    assert model['validated_subinterval']['interpolation_validated'] is True
    assert model['validated_subinterval']['minimum_command']==2385
    assert model['validated_subinterval']['maximum_command']==2389
    assert model['validated_subinterval']['heldout_commands']==[2388]
    assert model['validated_subinterval']['heldout_maximum_paired_error_counts']<=2
    assert model['validated_subinterval']['extrapolation_allowed'] is False


@pytest.mark.parametrize('fault',['sessions','route','missing','nonmonotonic','heldout'])
def test_incomplete_or_failed_generalization_is_rejected_or_not_released(fault):
    sessions=evidence()
    if fault=='sessions':sessions.pop()
    elif fault=='route':sessions[0][1]['target']=[0,0]
    elif fault=='missing':sessions[0].pop()
    elif fault=='nonmonotonic':
        for rows in sessions:rows[4]['actual']=[2384,1731]
    else:
        for rows in sessions:rows[1]['actual']=[2392,1722]
    if fault in ('sessions','route','missing','nonmonotonic'):
        with pytest.raises(ValueError):fit_local_interval(sessions,source_exports=['a','b','c'])
    else:
        assert fit_local_interval(sessions,source_exports=['a','b','c'])[
            'local_interval_interpolation_validated'] is False
