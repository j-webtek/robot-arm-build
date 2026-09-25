import math
import pytest
from rocell.arm.roll_history_assessment import assess_roll_history, CONTEXT


def row(name,t,error,**updates):
    r=dict.fromkeys(CONTEXT,'same')
    r.update(campaign_id=name,issued_ns=t,eligible=True,eligibility_reason='ELIGIBLE',
        start_rad=1.,target_rad=0.,final_rad=math.radians(error),error_deg=error,
        staged_start=[0,0,0,0,1,0],command=dict(T=101,joint=5,rad=0,spd=20,acc=1),
        configuration_sha256='same',spd=20,acc=1,direction='DECREASING')
    r.update(updates)
    return r


def test_chronological_holdout_never_trains_on_future_or_itself():
    result=assess_roll_history([row('c',3,.9),row('a',1,.1),row('b',2,.3)])
    p=result['chronological_error_predictions']
    assert p[0]['training_campaigns']==['a']
    assert p[0]['predicted_error_deg']==.1
    assert p[1]['training_campaigns']==['a','b']
    assert p[1]['predicted_error_deg']==pytest.approx(.2)
    assert result['deployment_status']=='NOT_VALIDATED_FOR_COMMAND_COMPENSATION'
    assert not result['motion_authorized']


def test_held_row_stays_visible_and_out_of_training():
    result=assess_roll_history([row('a',1,.1),row('bad',2,99,eligible=False,
        eligibility_reason='HISTORICAL_HOLD'),row('b',3,.3)])
    assert result['excluded']==[dict(campaign_id='bad',reason='HISTORICAL_HOLD')]
    assert result['chronological_error_predictions'][0]['training_campaigns']==['a']


@pytest.mark.parametrize('field',['schema','source_sha256','direction','spd','workcell_sha256'])
def test_context_changes_are_not_pooled(field):
    result=assess_roll_history([row('a',1,.1),row('b',2,.3,**{field:'different'})])
    assert not result['chronological_error_predictions']


def test_singleton_is_not_reported_as_zero_repeatability_error():
    group=assess_roll_history([row('a',1,.1)])['repeat_groups'][0]
    assert group['endpoint_spread_deg'] is None


def test_equal_timestamp_is_not_prior_training():
    assert not assess_roll_history([row('a',1,.1),row('b',1,.3)])['chronological_error_predictions']


def test_duplicate_and_nonfinite_rejected():
    with pytest.raises(ValueError):assess_roll_history([row('a',1,.1),row('a',2,.3)])
    with pytest.raises(ValueError):assess_roll_history([row('a',1,float('nan'))])


def test_spread_and_half_range_are_observed_not_future_bounds():
    result=assess_roll_history([row('a',1,.2),row('b',2,.4)])
    group=result['repeat_groups'][0]
    assert group['endpoint_spread_deg']==pytest.approx(.2)
    assert group['observed_best_constant_prediction_minimax_error_deg']==pytest.approx(.1)
    assert not result['uncertainty_bounds_for_future_trials_established']
