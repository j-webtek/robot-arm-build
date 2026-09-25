"""Offline three-startup release analysis for direct paired encoder motion."""
from __future__ import annotations

from .ghost_pair_transition_campaign import (
    DIRECT_TRANSITION_LEGS,PRIMARY_ROUTE,plan_ghost_pair_transition_campaign)


def analyze_ghost_pair_transitions(sessions,*,source_exports):
    """Reject incomplete, off-route or wrong-direction evidence without refitting."""
    if len(sessions)!=3 or len(source_exports)!=3 or len(set(source_exports))!=3:
        raise ValueError('Three independent session exports required')
    plan=plan_ghost_pair_transition_campaign()
    endpoint={2377:(2385,1730),2386:(2388,1727),
              2388:(2390,1725),2389:(2391,1724)}
    observations={leg:[] for leg in range(len(PRIMARY_ROUTE))}
    failures=[];direct=[]
    for session_index,rows in enumerate(sessions):
        if type(rows) is not list or len(rows)!=len(PRIMARY_ROUTE):
            raise ValueError('Complete twelve-leg session required')
        for leg,(row,command) in enumerate(zip(rows,PRIMARY_ROUTE)):
            if (row.get('leg')!=leg or row.get('target')!=[command,4114-command] or
                    type(row.get('actual')) is not list or len(row['actual'])!=2 or
                    row.get('assessment',{}).get('continuation_eligible') is not True):
                raise ValueError('Session route or continuation evidence differs')
            actual=row['actual'];observations[leg].append(actual)
            error=max(abs(a-e) for a,e in zip(actual,endpoint[command]))
            if error>2:failures.append({'session':session_index+1,'leg':leg,
                                        'reason':'ENDPOINT_ERROR','counts':error})
            if leg in {later for _,later in DIRECT_TRANSITION_LEGS}:
                previous=rows[leg-1]['actual']
                direction=1 if command>PRIMARY_ROUTE[leg-1] else -1
                primary_delta=actual[0]-previous[0]
                paired_delta=actual[1]-previous[1]
                direct.append({'session':session_index+1,'leg':leg,
                               'primary_delta':primary_delta,'paired_delta':paired_delta,
                               'endpoint_error_counts':error})
                if primary_delta*direction<1 or paired_delta*direction>0:
                    failures.append({'session':session_index+1,'leg':leg,
                                     'reason':'DIRECTION_OR_DISPLACEMENT'})
    maximum_spread=0
    for leg,values in observations.items():
        spread=max(max(value[j] for value in values)-min(value[j] for value in values)
                   for j in (0,1))
        maximum_spread=max(maximum_spread,spread)
        if spread>2:failures.append({'leg':leg,'reason':'REPEAT_SPREAD','counts':spread})
    return {'schema':'rocell.ghost_pair_transition_analysis.v1',
        'source_exports':list(source_exports),'source_plan_sha256':plan['plan_sha256'],
        'direct_transitions':direct,'maximum_repeat_spread_counts':maximum_spread,
        'failures':failures,'ghost_pair_cycle_validated':not failures,
        'continuous_motion_validated':False,'physical_contact_validated':False,
        'cartesian_accuracy_validated':False,'stylus_accuracy_validated':False,
        'movement_authorized':False}
