"""Offline descriptive/error-prediction screen; never an inverse motion model."""
from collections import defaultdict
import json
import math
from statistics import mean

CONTEXT=('schema','source_sha256','native_controller_review_sha256',
         'protocol_review_sha256','tool_payload_sha256','workcell_sha256',
         'bounded_motion_risk_sha256','spd','acc','direction')


def assess_roll_history(rows):
    """Use only earlier eligible trials for predictions; preserve exclusions.

    A mean observed error predicts error, not the result of adding its inverse
    to a command. Corrected commands need their own prospective validation.
    """
    ids=set()
    for r in rows:
        if r['campaign_id'] in ids:
            raise ValueError('Duplicate campaign')
        ids.add(r['campaign_id'])
        if type(r['issued_ns']) is not int or r['issued_ns']<=0:
            raise ValueError('Invalid ordering timestamp')
        for key in ('start_rad','target_rad','final_rad','error_deg'):
            value=r.get(key)
            if value is not None and (type(value) not in (int,float) or not math.isfinite(value)):
                raise ValueError('Nonfinite history value')
        if r['eligible'] and any(r.get(k) is None for k in ('start_rad','target_rad','final_rad','error_deg')):
            raise ValueError('Eligible trial lacks measurements')
    ordered=sorted(rows,key=lambda r:(r['issued_ns'],r['campaign_id']))
    eligible=[r for r in ordered if r['eligible']]
    groups=defaultdict(list)
    for r in eligible:
        # Runtime registration and per-run baseline hashes remain in dataset,
        # not equality keys: they identify distinct executions, not geometry.
        key=tuple(r[k] for k in CONTEXT)+(r['configuration_sha256'],
             json.dumps(r['staged_start']),json.dumps(r['command'],sort_keys=True))
        groups[key].append(r)
    repeats=[]
    for group in groups.values():
        values=[r['final_rad'] for r in group]
        spread=math.degrees(max(values)-min(values))
        repeats.append(dict(campaigns=[r['campaign_id'] for r in group],
            direction=group[0]['direction'],sample_count=len(group),
            start_rad=group[0]['start_rad'],target_rad=group[0]['target_rad'],
            endpoint_spread_deg=spread if len(group)>1 else None,
            observed_best_constant_prediction_minimax_error_deg=spread/2 if len(group)>1 else None,
            population_uncertainty_established=False))
    predictions=[]
    for current in eligible:
        training=[r for r in eligible if r['issued_ns']<current['issued_ns']
                  and all(r[k]==current[k] for k in CONTEXT)]
        if not training:
            continue
        predicted=mean(r['error_deg'] for r in training)
        predictions.append(dict(campaign_id=current['campaign_id'],direction=current['direction'],
            training_campaigns=[r['campaign_id'] for r in training],
            training_sample_count=len(training),
            training_distinct_targets=len({r['target_rad'] for r in training}),
            target_previously_observed=any(r['target_rad']==current['target_rad'] for r in training),
            predicted_error_deg=predicted,observed_error_deg=current['error_deg'],
            mean_bias_prediction_absolute_error_deg=abs(current['error_deg']-predicted),
            zero_bias_prediction_absolute_error_deg=abs(current['error_deg'])))
    score=None
    if predictions:
        score={name:dict(mae_deg=mean(p[key] for p in predictions),
                        maximum_absolute_error_deg=max(p[key] for p in predictions))
               for name,key in (('prior_mean_error','mean_bias_prediction_absolute_error_deg'),
                                ('zero_error','zero_bias_prediction_absolute_error_deg'))}
    return dict(schema='rocell.roll_history_assessment.v1',total_campaigns=len(rows),
        eligible_35s_campaigns=len(eligible),
        excluded=[dict(campaign_id=r['campaign_id'],reason=r['eligibility_reason']) for r in ordered if not r['eligible']],
        repeat_groups=repeats,chronological_error_predictions=predictions,prediction_scores=score,
        model_kind='PRIOR_DIRECTION_CONTEXT_MEAN_REPORTED_ERROR',
        scoring_scope='CONDITIONAL_ON_CLEAN_35S_PERSISTENT_RUNS_NOT_ALL_ATTEMPTS',
        prediction_is_corrected_command_validation=False,corrected_trials_executed=0,
        linear_model_status='NOT_FIT_TOO_FEW_INDEPENDENT_TARGETS_PER_DIRECTION_CONTEXT',
        deployment_status='NOT_VALIDATED_FOR_COMMAND_COMPENSATION',
        uncertainty_bounds_for_future_trials_established=False,
        motion_authorized=False,physical_accuracy_verified=False)
