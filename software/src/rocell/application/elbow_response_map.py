"""Offline comparison of bounded elbow trials; never creates motion authority."""
import itertools
import math
from .elbow_trace_analysis import analyze_elbow_trace


def build_response_map(sources):
    """Compare identical reported starting configurations, not unlike approaches.

    Inputs must come from the archive verifier. Host-observed plateaus do not
    establish sensor acquisition freshness or physical accuracy.
    """
    if not 2<=len(sources)<=12 or len({s['source_export'] for s in sources})!=len(sources):
        raise ValueError('Select 2–12 distinct verified trials')
    points=[]
    for source in sources:
        report=source['report']; trace=analyze_elbow_trace(report)
        tx=report['run']['transaction']; command=tx['command']
        baseline=tx['baseline_joints']; final=tx['rows'][-1][3]
        if (len(baseline)!=6 or len(final)!=6 or tx.get('command_attempts')!=1
                or any(type(v) not in (int,float) or not math.isfinite(v)
                       for v in [*baseline,*final,command['rad'],command['spd'],command['acc']])):
            raise ValueError('Finite complete single-command trial required')
        points.append(dict(source_export=source['source_export'],
            source_attachment_sha256=source['source_attachment_sha256'],
            baseline_joints=baseline,final_joints=final,command_rad=command['rad'],
            desired_rad=(tx.get('local_candidate') or {}).get('desired_rad'),
            wire_status=report['status'],desired_result=tx.get('desired_endpoint_result'),
            speed=command['spd'],acceleration=command['acc'],
            direction=1 if command['rad']>baseline[2] else -1 if command['rad']<baseline[2] else 0,
            reported_plateau=trace['classification'].startswith('REPORTED_PLATEAU_'),
            uncommanded_joints_unchanged=all(abs(a-b)<1e-8 for i,(a,b) in enumerate(zip(baseline,final)) if i!=2)))
    pairs=[]
    for a,b in itertools.combinations(points,2):
        comparable=(all(abs(x-y)<1e-8 for x,y in zip(a['baseline_joints'],b['baseline_joints']))
                    and (a['speed'],a['acceleration'],a['direction'])==(b['speed'],b['acceleration'],b['direction'])
                    and a['direction']!=0 and a['reported_plateau'] and b['reported_plateau']
                    and a['uncommanded_joints_unchanged'] and b['uncommanded_joints_unchanged'])
        pair=dict(sources=[a['source_export'],b['source_export']],comparable=comparable)
        if comparable:
            dx=b['command_rad']-a['command_rad']; dy=b['final_joints'][2]-a['final_joints'][2]
            pair.update(command_difference_rad=dx,endpoint_difference_rad=dy,
                secant_gain=None if abs(dx)<1e-9 else dy/dx,
                classification=('REPEATED_COMMAND' if abs(dx)<1e-9 else
                                'REPORTED_PLATEAU' if abs(dy)<1e-9 else
                                'MONOTONIC_PAIR' if dx*dy>0 else 'NONMONOTONIC_PAIR'))
        else:
            pair['classification']='NOT_COMPARABLE'
        pairs.append(pair)
    return dict(schema='rocell.elbow_response_map.v1',points=points,pairs=pairs,
                comparable_pairs=sum(p['comparable'] for p in pairs),
                inverse_model_qualified=False,physical_accuracy_verified=False,
                hardware_access=False,motion_authorized=False)
