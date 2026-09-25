from copy import deepcopy
import pytest
from rocell.application.matrix_model_review import compare_models


def rows():
    targets=[(2385,1729),(2389,1725),(2381,1733),(2389,1725),(2377,1737),(2389,1725),(2385,1729),(2389,1725)]
    actual=[(2395,1722),(2395,1722),(2391,1726),(2391,1724),(2386,1730),(2391,1724),(2391,1724),(2391,1724)]
    result=[]; before=(2398,1718); previous=(2389,1725)
    for index,(target,end) in enumerate(zip(targets,actual)):
        result.append(dict(leg=index,target=target,before=before,actual=end,
                           goal_delta=[g-p for g,p in zip(target,previous)]))
        before=end;previous=target
    return result


def test_frozen_fit_and_small_only_holdout():
    result=compare_models(rows())
    assert result['training_legs']==list(range(6)) and result['held_out_legs']==[6,7]
    assert result['bands'][0]==pytest.approx([2,29/3])
    assert result['bands'][1]==[-7,-1]
    assert result['held_out_metrics']['stateful_band']['maximum_absolute_error_counts']==0
    assert not result['held_out_contains_clear_motion']
    assert not result['compensation_authorized']


def test_holdout_never_changes_fit():
    original=rows(); changed=deepcopy(original);changed[-1]['actual']=(2393,1723)
    a,b=compare_models(original),compare_models(changed)
    for key in ('constant_residual','directional_residual','bands','clear_response_band_edges'):
        assert a[key]==b[key]
    assert a['held_out_metrics']!=b['held_out_metrics']


@pytest.mark.parametrize('fault',['duplicate','no_holdout','no_direction','coupling'])
def test_invalid_evidence(fault):
    data=rows()
    if fault=='duplicate':data[-1]['leg']=6
    if fault=='no_holdout':data=data[:6]
    if fault=='no_direction':
        for r in data:r['goal_delta']=(-4,4)
    if fault=='coupling':data[0]['target']=(2385,1730)
    with pytest.raises(ValueError):compare_models(data)
