"""Frozen repeat-validation plan for two local fine endpoint candidates."""
from __future__ import annotations

import hashlib
import json


PRIMARY_TARGETS=(2377,2385,2389,2377,2385,2389,
                 2377,2388,2389,2377,2388,2389)
PAIR_SUM=4114
INITIAL_GOALS=(2387,1727)
INITIAL_POSITIONS=(2389,1726)
INITIAL_TOLERANCE=1


def _canonical(value):
    return json.dumps(value,sort_keys=True,separators=(',',':')).encode()


def plan_fine_lookup_validation():
    goals=[[primary,PAIR_SUM-primary] for primary in PRIMARY_TARGETS]
    roles=['condition_lower','candidate_2387','condition_upper',
           'condition_lower','heldout_2387','condition_upper',
           'condition_lower','candidate_2389','condition_upper',
           'condition_lower','heldout_2389','condition_upper']
    plan={'schema':'rocell.fine_pair_lookup_validation.v1','revision':50,
        'purpose':'repeat_two_fine_candidates_from_validated_lower_plateau',
        'source_mapping_export':'wizard-20260920T224608597099Z-151dafd0c1d547a9bc323d28db5cc550',
        'source_plateau_policy':'wizard-20260920T225030977676Z-49605b8c62e2470bb558a7bf8d0e5a5e',
        'initial_gate':{'goals':list(INITIAL_GOALS),'positions':list(INITIAL_POSITIONS),
                        'position_tolerance_counts':INITIAL_TOLERANCE},
        'manifest':{'goals':goals,'roles':roles,'legs':12,'pair_sum':PAIR_SUM},
        'comparisons':[
            {'desired_positions':[2387,1727],'candidate_goals':[2385,1729],
             'source_training_leg':2,'candidate_leg':1,'heldout_leg':4,
             'direct_control_goals':[2387,1727],
             'retained_direct_control_actual':[2389,1726]},
            {'desired_positions':[2389,1725],'candidate_goals':[2388,1726],
             'source_training_leg':6,'candidate_leg':7,'heldout_leg':10,
             'direct_control_goals':[2389,1725],
             'retained_direct_control_actual':[2391,1724]}],
        'limits':{'writes':12,'writes_per_leg':1,'maximum_step_counts':12,
                  'automatic_retry':False,'automatic_return':False},
        'release_rule':{'both_candidate_repeats_required':True,
                        'maximum_candidate_endpoint_error_counts':1,
                        'must_improve_over_retained_direct_control':True,
                        'anchor_transition_failure_stops':True},
        'claims':{'fine_endpoint_lookup_validated':False,
                  'general_compensation_validated':False,
                  'cartesian_accuracy_validated':False,
                  'stylus_accuracy_validated':False,
                  'movement_authorized':False,'hardware_access_during_planning':False}}
    plan['plan_sha256']=hashlib.sha256(_canonical(plan)).hexdigest()
    return plan
