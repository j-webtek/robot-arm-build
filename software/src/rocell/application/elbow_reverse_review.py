"""Audit reverse response without inferring servo-bus delivery or physical cause."""
import math
from .wrist_command_comparison import summarize_joint_trial
from .controller_route_preview import _baseline
from .asynchronous_response_review import review_response_envelope
from rocell.safety.wifi_all_joint_reservation import verify_sample


def review_reverse_identification(report, passive, model):
    summary=summarize_joint_trial(report,joint=3)
    if summary['elbow']['ideal_delta_deg']>=0:
        raise ValueError('Reverse elbow trial required')
    tx=report['transaction'];rows=tx['rows']
    if report.get('acknowledgment_received') is not True:
        raise ValueError('Acknowledged trial required for this comparison')
    previous=tx['dispatch_s']
    for row in rows:
        raw=row['raw_feedback'];verify_sample(raw)
        _,q,consistent=_baseline(raw)
        if (not consistent or q!=row['reported_joints_rad']
                or row['observed_s']!=raw['response_finished_monotonic_s']
                or not previous<row['observed_s']<=tx['dispatch_s']+10):
            raise ValueError('Ordered consistent raw trial feedback required')
        previous=row['observed_s']
    samples=passive['samples']
    if passive.get('motion_commands')!=0 or not samples:
        raise ValueError('Nonempty feedback-only follow-up required')
    loads=[];positions=[]
    for raw in samples:
        verify_sample(raw)
        _,q,consistent=_baseline(raw)
        begin=raw['request_started_monotonic_s'];end=raw['response_finished_monotonic_s']
        if not consistent or not previous<begin<=end:
            raise ValueError('Follow-up must follow trial on the same monotonic clock')
        previous=end;positions.append(q)
        load=raw.get('servo_status',{}).get('loads_raw',{}).get('elbow')
        if type(load) in (int,float) and math.isfinite(load):loads.append(load)
    final=summary['final_joints_rad']
    # Quantify an older-offset transfer as a scenario, never an executable fit.
    desired=list(final);desired[2]=summary['command']['rad']
    historical_bias=0.047382961599716555
    transferred=list(desired);transferred[2]-=historical_bias
    return dict(schema='rocell.elbow_reverse_review.v1',trial=summary,
        passive_samples=len(samples),
        passive_span_s=samples[-1]['response_finished_monotonic_s']-samples[0]['response_finished_monotonic_s'],
        maximum_passive_joint_change_rad=max(abs(a-b) for q in positions for a,b in zip(q,final)),
        passive_elbow_load_range_raw=[min(loads),max(loads)] if loads else None,
        historical_offset_scenario=dict(bias_rad=historical_bias,target_rad=transferred[2],
            envelope=review_response_envelope(model,final,transferred,extra_steps=1)),
        servo_bus_delivery_verified=False,physical_cause_established=False,
        load_is_calibrated_force=False,compensation_enabled=False,motion_authorized=False,
        conclusion='HTTP receipt and unchanged feedback do not distinguish load, backlash, servo control deadband or installed-firmware behavior.')
