"""Frozen three-startup plan for a five-command local shoulder interval."""
from __future__ import annotations

import hashlib
import json


PAIR_SUM=4114
ENDPOINT_COMMANDS=(2377,2383,2385,2388,2389)
ROUTE=(2377,2383,2389,2377,2385,2389,2377,2388,2389,2377,2389)
SAMPLE_LEGS=(0,1,4,7,10)
TRAINING_COMMANDS=(2377,2385,2389)
HELDOUT_COMMANDS=(2383,2388)


def _canonical(value):
    return json.dumps(value,sort_keys=True,separators=(',',':')).encode()


def plan_local_interval_campaign():
    goals=[[primary,PAIR_SUM-primary] for primary in ROUTE]
    manifest={'goals':goals,'legs':len(goals),'pair_sum':PAIR_SUM,
              'roles':['sample_2377','sample_2383','condition_upper','condition_lower',
                       'sample_2385','condition_upper','condition_lower','sample_2388',
                       'condition_upper','condition_lower','sample_2389']}
    value={'schema':'rocell.local_interval_campaign.v1','candidate_revision':51,
        'purpose':'five_endpoint_piecewise_local_interval_validation',
        'sessions':3,'fresh_startup_per_session':True,
        'initial_gate':{'goals':[2389,1725],'positions':[2391,1724],
                        'position_tolerance_counts':1},
        'manifest':manifest,'sample_legs':list(SAMPLE_LEGS),
        'endpoint_commands':list(ENDPOINT_COMMANDS),
        'training_commands':list(TRAINING_COMMANDS),
        'heldout_commands':list(HELDOUT_COMMANDS),
        'release_rule':{
            'minimum_samples_per_endpoint':3,
            'minimum_startups':2,
            'strictly_monotonic_training_endpoints':True,
            'heldout_maximum_paired_error_counts':2,
            'heldout_p95_paired_error_counts':2,
            'extrapolation_allowed':False},
        'limits':{'writes_per_session':len(goals),'writes_per_leg':1,
                  'automatic_retry':False,'automatic_return':False},
        'claims':{'local_interval_interpolation_validated':False,
                  'general_workspace_compensation_validated':False,
                  'movement_authorized':False,'hardware_access_during_planning':False}}
    value['plan_sha256']=hashlib.sha256(_canonical(value)).hexdigest()
    return value
