import math
import pytest
from rocell.arm.sustained_band import assess_sustained_band


def assess(values, times=None, **kwargs):
    times = times if times is not None else [i*.5 for i in range(len(values))]
    samples = [dict(request_started_monotonic_s=t,
        response_finished_monotonic_s=t+.1, joints_rad=dict(r=math.radians(v)))
        for t,v in zip(times,values)]
    return assess_sustained_band(samples,desired_rad=math.radians(1.5),
        band_deg=.05,required_duration_s=1,**kwargs)


def test_duration_uses_bounds_not_count():
    assert not assess([1.5]*3)['final_sampled_run_qualifies']
    r=assess([1.5]*4)
    assert r['entire_sampled_window_qualifies']
    assert r['final_in_band_run_s']==pytest.approx(1.4)


def test_late_change_and_return_require_new_run():
    r=assess([1.5]*4+[1.4,1.5])
    assert r['longest_in_band_run_s']==pytest.approx(1.4)
    assert not r['final_sampled_run_qualifies']
    r=assess([1.4]+[1.5]*4)
    assert r['final_sampled_run_qualifies']
    assert not r['entire_sampled_window_qualifies']


def test_gap_breaks_even_all_in_band():
    r=assess([1.5]*4,times=[0,.5,2,2.5])
    assert r['gap_break_sample_indices']==[2]
    assert not r['final_sampled_run_qualifies']
    assert not r['entire_sampled_window_qualifies']


def test_single_sample_never_duration():
    assert assess([1.5])['final_in_band_run_s']==0


@pytest.mark.parametrize('times',[[0,-1],[0,.05],[0,float('nan')]])
def test_bad_timestamps(times):
    with pytest.raises(ValueError):assess([1.5]*2,times=times)


@pytest.mark.parametrize('gap',[0,-1,float('inf'),True])
def test_bad_settings(gap):
    with pytest.raises(ValueError):assess([1.5],maximum_gap_s=gap)


def test_empty_and_nonfinite():
    with pytest.raises(ValueError):assess([])
    with pytest.raises(ValueError):assess([float('nan')])


def test_requested_capture_duration_is_not_observed_duration():
    samples=[dict(request_started_monotonic_s=i*.5,
        response_finished_monotonic_s=i*.5+.1,joints_rad=dict(r=0))
        for i in range(70)]
    r=assess_sustained_band(samples,desired_rad=0,band_deg=.1,required_duration_s=35)
    assert r['all_samples_in_band']
    assert not r['entire_sampled_window_qualifies']
