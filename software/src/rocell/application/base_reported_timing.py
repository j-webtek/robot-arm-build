"""Compact timing over validated controller reports, never physical timestamps."""
import math


def summarize_reported_base_timing(rows, *, start_rad, desired_rad, write_finished_ns):
    """Keep acquisition bounds and constant-value runs instead of invented rates.

    The export reader validates transport, ownership and full capture first.
    This summary describes host observations only: buffering and device sample
    freshness are not independently measured, so no servo-speed claim is made.
    """
    if (type(rows) is not list or not 20<=len(rows)<=4096
            or type(write_finished_ns) is not int
            or any(type(v) not in (int,float) or not math.isfinite(v) for v in (start_rad,desired_rad))):
        raise ValueError('Bounded validated timing input required')
    runs=[];previous=None;first_changed=None;first_band=None
    maximum_gap=0
    for begin,end,joints in rows:
        if (type(begin) is not int or type(end) is not int or not write_finished_ns<=begin<=end
                or len(joints)!=6 or any(type(v) not in (int,float) or not math.isfinite(v) for v in joints)
                or (previous is not None and (begin<previous[0] or end<previous[1]))):
            raise ValueError('Invalid acquisition bounds or joint values')
        value=joints[0]
        bounds=[begin-write_finished_ns,end-write_finished_ns]
        if previous is not None:maximum_gap=max(maximum_gap,begin-previous[1])
        if first_changed is None and abs(value-start_rad)>1e-12:first_changed=bounds
        if first_band is None and abs(value-desired_rad)<=math.radians(.25):first_band=bounds
        if not runs or value!=runs[-1]['reported_base_rad']:
            runs.append(dict(reported_base_rad=value,first_acquisition_after_write_ns=bounds,
                last_acquisition_after_write_ns=bounds,sample_count=1))
        else:
            runs[-1]['last_acquisition_after_write_ns']=bounds
            runs[-1]['sample_count']+=1
        previous=(begin,end)
    final=runs[-1]
    return dict(schema='rocell.reported_base_timing.v1',
        first_changed_report_after_write_ns=first_changed,
        first_report_in_quarter_degree_band_after_write_ns=first_band,
        final_constant_run_entry_after_write_ns=final['first_acquisition_after_write_ns'],
        final_constant_run_observed_span_ns=max(0,final['last_acquisition_after_write_ns'][0]-final['first_acquisition_after_write_ns'][1]),
        maximum_inter_report_acquisition_gap_ns=maximum_gap,reported_transition_count=len(runs)-1,
        runs=runs,device_sample_freshness_verified=False,physical_timing_verified=False,
        motion_authorized=False)
