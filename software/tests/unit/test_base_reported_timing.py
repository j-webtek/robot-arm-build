import math
import pytest
from rocell.application.base_reported_timing import summarize_reported_base_timing


def records():
    return [(100+i*20,110+i*20,[math.radians(0 if i<5 else .5 if i<10 else 1),0,0,0,0,0]) for i in range(30)]


def test_preserves_acquisition_bounds_and_constant_runs():
    r=summarize_reported_base_timing(records(),start_rad=0,desired_rad=math.radians(1),write_finished_ns=100)
    assert r['first_changed_report_after_write_ns']==[100,110]
    assert r['first_report_in_quarter_degree_band_after_write_ns']==[200,210]
    assert r['final_constant_run_entry_after_write_ns']==[200,210]
    assert r['reported_transition_count']==2
    assert [x['sample_count'] for x in r['runs']]==[5,5,20]
    assert r['maximum_inter_report_acquisition_gap_ns']==10
    assert not r['physical_timing_verified']


def test_unchanged_reports_do_not_invent_response():
    rows=[(begin,end,[0.]*6) for begin,end,_ in records()]
    r=summarize_reported_base_timing(rows,start_rad=0,desired_rad=1,write_finished_ns=100)
    assert r['first_changed_report_after_write_ns'] is None
    assert r['first_report_in_quarter_degree_band_after_write_ns'] is None
    assert r['reported_transition_count']==0


def test_single_last_report_has_no_proven_constant_duration():
    rows=records();rows[-1][2][0]=math.radians(1.05)
    r=summarize_reported_base_timing(rows,start_rad=0,desired_rad=math.radians(1),write_finished_ns=100)
    assert r['final_constant_run_observed_span_ns']==0


@pytest.mark.parametrize('fault',['short','prewrite','reordered','nan'])
def test_invalid_timing_input_rejected(fault):
    rows=records()
    if fault=='short':rows=rows[:5]
    if fault=='prewrite':rows[0]=(99,110,[0.]*6)
    if fault=='reordered':rows[2]=rows[0]
    if fault=='nan':rows[2][2][0]=float('nan')
    with pytest.raises(ValueError):summarize_reported_base_timing(rows,start_rad=0,desired_rad=1,write_finished_ns=100)
