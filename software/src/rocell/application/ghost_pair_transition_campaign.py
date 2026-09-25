"""Frozen campaign for validating direct upper-interval ghost-key transitions."""
from __future__ import annotations

import hashlib

from .first_motion_contract import canonical

PAIR_SUM=4114
PRIMARY_ROUTE=(2377,2386,2388,2386,2388,2386,
               2377,2386,2388,2386,2388,2389)
DIRECT_TRANSITION_LEGS=((1,2),(2,3),(3,4),(4,5),(7,8),(8,9),(9,10))


def plan_ghost_pair_transition_campaign():
    """Return an immutable, non-authorizing three-startup transition campaign."""
    goals=[[primary,PAIR_SUM-primary] for primary in PRIMARY_ROUTE]
    value={
        'schema':'rocell.ghost_pair_transition_campaign.v1',
        'purpose':'validate_direct_hover_press_retract_encoder_transitions',
        'required_sessions':3,
        'manifest':{'legs':len(goals),'goals':goals,
                    'maximum_writes_per_session':12,'automatic_retry':False},
        'start_gate':{'goals':[2389,1725],'positions':[2391,1724],
                      'position_tolerance_counts':1,'fresh_feedback_required':True},
        'conditioned_lower':{'command_goals':[2377,1737],
            'expected_positions':{'minimum':[2385,1730],'maximum':[2386,1731]}},
        'hover':{'command_goals':[2386,1728],'expected_positions':[2388,1727]},
        'press':{'command_goals':[2388,1726],'expected_positions':[2390,1725]},
        'upper_terminal':{'command_goals':[2389,1725],
                          'expected_positions':[2391,1724]},
        'direct_transition_legs':[list(pair) for pair in DIRECT_TRANSITION_LEGS],
        'release_rule':{
            'maximum_endpoint_error_counts':2,
            'maximum_repeat_spread_counts':2,
            'minimum_primary_displacement_counts':1,
            'direction_must_match_command':True,
            'all_sessions_complete':True,
            'no_faults_or_retries':True,
        },
        'small_response_policy':{
            'ordinary_global_relaxation':False,
            'exact_manifest_only':True,
            'continue_only_after_fresh_endpoint_verification':True,
            'maximum_consecutive_direct_transitions':4,
            'stop_on_out_of_tolerance_or_wrong_direction':True,
        },
        'claims':{
            'direct_transition_validation_required':True,
            'ghost_pair_cycle_validated':False,
            'continuous_motion_validated':False,
            'physical_contact_requested':False,
            'cartesian_accuracy_validated':False,
            'stylus_accuracy_validated':False,
            'movement_authorized':False,
        },
    }
    value['plan_sha256']=hashlib.sha256(canonical(value)).hexdigest()
    return value
