import copy
import pytest
from test_product_ghost_controller_bridge import source
from rocell.application.product_ghost_interpolation import screen_product_ghost


def test_screen_is_deterministic_offline_and_keeps_semantics():
    data=source(); before=copy.deepcopy(data)
    result=screen_product_ghost(data)
    assert result['status']=='REFERENCE_INTERPOLATION_PASS'
    assert result['evaluated_legs']==result['planned_legs']==1
    assert result['total_samples']>2
    assert result['legs'][0]['target_key']=='keyboard:A'
    assert not result['hardware_access'] and not result['motion_authorized']
    assert not result['timing_available'] and not result['tool_clearance_verified']
    assert data==before and screen_product_ghost(data)==result


@pytest.mark.parametrize('spd',[True,0,2,float('nan'),float('inf')])
def test_bad_speed_rejected(spd):
    with pytest.raises(ValueError): screen_product_ghost(source(),spd=spd)


def test_reference_failure_stops_progression(monkeypatch):
    import rocell.application.product_ghost_interpolation as module
    data=source()
    route=data['dense_route']['round']
    third=copy.deepcopy(route['joint_results'][-1]); third['waypoint_sequence']=2
    route['joint_results'].append(third)
    route['waypoint_count']=route['evaluated_waypoint_count']=3
    monkeypatch.setattr(module,'_screen_reference_trace',lambda trace: {'status':'REFERENCE_IK_UNRESOLVED'})
    result=screen_product_ghost(data)
    assert result['status']=='REFERENCE_INTERPOLATION_INCOMPLETE'
    assert result['evaluated_legs']==1 and result['planned_legs']==2


def test_trace_budget_failure_is_not_a_pass(monkeypatch):
    import rocell.application.product_ghost_interpolation as module
    def unavailable(*args, **kwargs):
        raise ValueError('sample budget')
    monkeypatch.setattr(module,'simulate_t104_trace',unavailable)
    result=screen_product_ghost(source())
    assert result['status']=='REFERENCE_INTERPOLATION_INCOMPLETE'
    assert result['legs'][0]['status']=='TRACE_UNAVAILABLE'
