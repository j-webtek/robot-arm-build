"""Compose a bounded encoder-space hover/press/retract candidate.

Each endpoint is supported by the local interval policy.  The direct transitions
between them remain held out, so this module produces a preview, never authority.
"""
from __future__ import annotations

from .local_interval_command_policy import resolve_interval_endpoint


def plan_ghost_pair_cycle(policy,*,current_goals,current_positions,
                          hover_positions,press_positions):
    """Plan the smallest useful 'molecule' from independently validated atoms."""
    hover=resolve_interval_endpoint(policy,current_goals=current_goals,
        current_positions=current_positions,desired_positions=hover_positions)
    press=resolve_interval_endpoint(policy,current_goals=current_goals,
        current_positions=current_positions,desired_positions=press_positions)
    if hover['resolution_mode']!='UPPER_INTERVAL_INTERPOLATION' or \
            press['resolution_mode']!='UPPER_INTERVAL_INTERPOLATION':
        raise ValueError('Ghost cycle requires two interpolated upper-interval endpoints')
    if hover['command_goals']==press['command_goals']:
        raise ValueError('Hover and press commands must differ')
    delta=[b-a for a,b in zip(hover['command_goals'],press['command_goals'])]
    if max(abs(value) for value in delta)>2:
        raise ValueError('Candidate transition exceeds two encoder counts')
    steps=[
        {'phase':'HOVER','resolution':hover},
        {'phase':'PRESS','resolution':press},
        {'phase':'RETRACT','resolution':hover},
    ]
    return {
        'schema':'rocell.ghost_pair_cycle_candidate.v1',
        'status':'PREVIEW_ONLY_DIRECT_TRANSITIONS_UNVALIDATED',
        'steps':steps,
        'transition_deltas':[delta,[-value for value in delta]],
        'endpoint_policy_validated':True,
        'direct_transition_validation_required':True,
        'continuous_motion_validated':False,
        'physical_contact_requested':False,
        'cartesian_accuracy_validated':False,
        'stylus_accuracy_validated':False,
        'movement_authorized':False,
        'automatic_retry':False,
    }
