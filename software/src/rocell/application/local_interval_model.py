"""Piecewise-linear local interval fit and held-out scoring."""
from __future__ import annotations

from statistics import median

from .local_interval_campaign import (
    ENDPOINT_COMMANDS,HELDOUT_COMMANDS,ROUTE,SAMPLE_LEGS,TRAINING_COMMANDS,
    plan_local_interval_campaign)


def _lerp(x,x0,x1,y0,y1):
    return y0+(x-x0)*(y1-y0)/(x1-x0)


def _percentile95(values):
    ordered=sorted(values)
    return ordered[max(0,(95*len(ordered)+99)//100-1)]


def _score_heldout(samples,centers,training_commands,heldout_commands):
    """Score held-out commands without allowing them to influence the fit."""
    training=[(command,centers[command]) for command in training_commands]
    if any(not training[i][1][0]<training[i+1][1][0] for i in range(len(training)-1)):
        return {'training_monotonic':False,'heldout':[],
                'maximum_error_counts':None,'p95_error_counts':None}
    errors=[];heldout=[]
    for command in heldout_commands:
        left,right=next((training[i],training[i+1]) for i in range(len(training)-1)
                        if training[i][0]<command<training[i+1][0])
        predicted=[_lerp(command,left[0],right[0],left[1][j],right[1][j]) for j in (0,1)]
        endpoint_errors=[]
        for actual in samples[command]:
            paired=max(abs(actual[j]-predicted[j]) for j in (0,1))
            errors.append(paired);endpoint_errors.append(paired)
        heldout.append({'command_goals':[command,4114-command],
            'predicted_positions':predicted,'observed_positions':samples[command],
            'paired_errors_counts':endpoint_errors})
    return {'training_monotonic':True,'heldout':heldout,
            'maximum_error_counts':max(errors),'p95_error_counts':_percentile95(errors)}


def fit_local_interval(sessions,*,source_exports):
    """Fit training anchors and score completely held-out command locations."""
    plan=plan_local_interval_campaign()
    if len(sessions)!=3 or len(source_exports)!=3:
        raise ValueError('Exactly three startup sessions required')
    samples={command:[] for command in ENDPOINT_COMMANDS}
    for session_index,rows in enumerate(sessions):
        if type(rows) is not list or len(rows)!=len(ROUTE):
            raise ValueError('Complete local interval session required')
        for leg,(row,command) in enumerate(zip(rows,ROUTE)):
            if (row.get('leg')!=leg or row.get('target')!=[command,4114-command] or
                    type(row.get('actual')) is not list or len(row['actual'])!=2):
                raise ValueError('Local interval row differs from frozen route')
        for leg,command in zip(SAMPLE_LEGS,ENDPOINT_COMMANDS):
            samples[command].append(rows[leg]['actual'])
    if any(len(values)<plan['release_rule']['minimum_samples_per_endpoint']
           for values in samples.values()):
        raise ValueError('Insufficient endpoint repetitions')

    centers={command:[median(value[j] for value in samples[command]) for j in (0,1)]
             for command in ENDPOINT_COMMANDS}
    full_score=_score_heldout(samples,centers,TRAINING_COMMANDS,HELDOUT_COMMANDS)
    if not full_score['training_monotonic']:
        raise ValueError('Training endpoints are not strictly monotonic')
    maximum=full_score['maximum_error_counts'];p95=full_score['p95_error_counts']
    released=(maximum<=plan['release_rule']['heldout_maximum_paired_error_counts'] and
              p95<=plan['release_rule']['heldout_p95_paired_error_counts'])

    # If the full span fails, classify the predeclared useful upper span separately.
    # Command 2388 remains wholly held out from the two-anchor 2385..2389 fit.
    upper_score=_score_heldout(samples,centers,(2385,2389),(2388,))
    upper_released=(upper_score['training_monotonic'] and
        upper_score['maximum_error_counts']<=plan['release_rule']['heldout_maximum_paired_error_counts'] and
        upper_score['p95_error_counts']<=plan['release_rule']['heldout_p95_paired_error_counts'])
    return {'schema':'rocell.local_interval_model.v1','source_exports':list(source_exports),
        'source_plan_sha256':plan['plan_sha256'],'centers':[
            {'command_goals':[command,4114-command],'observed_position_center':centers[command]}
            for command in ENDPOINT_COMMANDS],
        'training_commands':list(TRAINING_COMMANDS),'heldout':full_score['heldout'],
        'heldout_maximum_paired_error_counts':maximum,
        'heldout_p95_paired_error_counts':p95,
        'local_interval_interpolation_validated':released,
        'domain':{'minimum_command':min(ENDPOINT_COMMANDS),
                  'maximum_command':max(ENDPOINT_COMMANDS),'extrapolation_allowed':False},
        'validated_subinterval':{
            'minimum_command':2385,'maximum_command':2389,
            'training_commands':[2385,2389],'heldout_commands':[2388],
            'training_monotonic':upper_score['training_monotonic'],
            'heldout':upper_score['heldout'],
            'heldout_maximum_paired_error_counts':upper_score['maximum_error_counts'],
            'heldout_p95_paired_error_counts':upper_score['p95_error_counts'],
            'interpolation_validated':upper_released,'extrapolation_allowed':False},
        'movement_authorized':False,'cartesian_accuracy_validated':False,
        'stylus_accuracy_validated':False}
