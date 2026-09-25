import math
import pytest
from rocell.application.elbow_trace_analysis import analyze_elbow_trace


def source(values):
    return dict(schema='rocell.native_cartesian_trial.v1',status='COMPLETION_DEADLINE_EXCEEDED',run=dict(transaction=dict(
        command=dict(T=101,joint=3,rad=1-math.radians(5)),dispatch_started_ns=1_000_000_000,
        baseline_joints=[0,0,1,0,0,0],rows=[
            [1_000_000_000+i*1_000_000_000,1_100_000_000+i*1_000_000_000,[0,0,0,0],[0,0,v,0,0,0]]
            for i,v in enumerate(values)])))


def test_early_change_then_plateau_is_not_verified_settling():
    r=analyze_elbow_trace(source([1,.97,.965,.965,.965,.965,.965]))
    assert r['classification']=='REPORTED_PLATEAU_WITH_SHORTFALL'
    assert r['last_reported_change_s']==2.1
    assert r['unchanged_tail_s']==pytest.approx(4)
    assert r['final_two_second_span_deg']==0
    assert not r['physical_settling_verified'] and not r['servo_acquisition_freshness_verified']


def test_ongoing_change_is_not_plateau():
    assert analyze_elbow_trace(source([1,.99,.98,.97,.96]))['classification']=='REVIEW_TRACE'


def test_reverse_direction_overshoot_is_not_shortfall():
    data=source([1,1.05,1.06,1.06,1.06,1.06])
    data['run']['transaction']['command']['rad']=1.05
    result=analyze_elbow_trace(data)
    assert result['response_relation']=='OVERSHOOT'
    assert result['classification']=='REPORTED_PLATEAU_WITH_OVERSHOOT'


def test_unordered_rows_rejected():
    r=source([1,.97,.96]); r['run']['transaction']['rows'].reverse()
    with pytest.raises(ValueError): analyze_elbow_trace(r)
