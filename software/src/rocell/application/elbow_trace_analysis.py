"""Analyze retained elbow telemetry timing, not physical settling or bus freshness."""
import math


def analyze_elbow_trace(report):
    tx=(report.get('run') or {}).get('transaction') or {}
    command=tx.get('command') or {}
    if report.get('schema')!='rocell.native_cartesian_trial.v1' or command.get('T')!=101 or command.get('joint')!=3:
        raise ValueError('Native single-elbow trial required')
    rows=tx.get('rows')
    if type(rows) is not list or not 2<=len(rows)<=128:
        raise ValueError('Bounded retained observation series required')
    start=tx['dispatch_started_ns']; baseline=tx['baseline_joints'][2]; target=command['rad']
    if type(start) is not int or any(type(v) not in (float,int) or not math.isfinite(v) for v in (baseline,target)):
        raise ValueError('Finite baseline and dispatch time required')
    samples=[]; previous_end=start; previous=baseline; last_change=None
    for row in rows:
        if type(row) is not list or len(row)!=4 or len(row[3])!=6:
            raise ValueError('Invalid retained row')
        begin,end,_,joints=row; value=joints[2]
        if (type(begin) is not int or type(end) is not int or not previous_end<=begin<=end
                or type(value) not in (float,int) or not math.isfinite(value)):
            raise ValueError('Invalid time ordering or elbow value')
        elapsed=(end-start)/1e9
        if abs(value-previous)>1e-9: last_change=elapsed
        samples.append(dict(host_elapsed_s=elapsed,elbow_rad=value))
        previous=value; previous_end=end
    final=samples[-1]; tail=[s['elbow_rad'] for s in samples if s['host_elapsed_s']>=final['host_elapsed_s']-2]
    residual=math.degrees(final['elbow_rad']-target)
    requested=target-baseline
    relation=('AT_TARGET' if abs(residual)<=.1 else
              'OVERSHOOT' if residual*requested>0 else 'SHORTFALL')
    tail_span=math.degrees(max(tail)-min(tail))
    plateau=last_change is not None and final['host_elapsed_s']-last_change>=2 and len(tail)>=3 and tail_span<.01
    return dict(schema='rocell.elbow_trace_analysis.v1',source_status=report['status'],
        classification=f'REPORTED_PLATEAU_WITH_{relation}' if plateau and abs(residual)>.1 else 'REVIEW_TRACE',
        response_relation=relation,
        requested_delta_deg=math.degrees(target-baseline),reported_delta_deg=math.degrees(final['elbow_rad']-baseline),
        residual_deg=residual,first_observation_s=samples[0]['host_elapsed_s'],
        last_observation_s=final['host_elapsed_s'],last_reported_change_s=last_change,
        unchanged_tail_s=None if last_change is None else final['host_elapsed_s']-last_change,
        final_two_second_samples=len(tail),final_two_second_span_deg=tail_span,
        distinct_elbow_values=len(set(s['elbow_rad'] for s in samples)),samples=samples,
        physical_settling_verified=False,servo_acquisition_freshness_verified=False,
        hardware_access=False,motion_authorized=False,
        interpretation='Host-timed reported trajectory only; identical final samples may be cached. No fitted correction.')
