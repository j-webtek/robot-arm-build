"""Bounded endpoint resolver composed from anchor and r50 lookup evidence."""
from __future__ import annotations

from copy import deepcopy


def derive_endpoint_policy(anchor_policy,lookup_analysis,*,lookup_analysis_export):
    if (anchor_policy.get('schema')!='rocell.local_pair_plateau_policy.v1' or
            anchor_policy.get('encoder_anchor_navigation_validated') is not True or
            anchor_policy.get('heldout',{}).get('passed') is not True):
        raise ValueError('Validated anchor policy required')
    if (lookup_analysis.get('schema')!='rocell.fine_pair_lookup_analysis.v1' or
            lookup_analysis.get('fine_endpoint_lookup_validated') is not True or
            lookup_analysis.get('movement_authorized') is not False):
        raise ValueError('Validated non-authorizing lookup analysis required')
    entries=lookup_analysis.get('entries')
    if type(entries) is not list or len(entries)!=2 or not all(
            entry.get('validated') is True for entry in entries):
        raise ValueError('Exactly two validated endpoint lookups required')
    lower=anchor_policy['rules']['lower']
    rules={}
    for entry in entries:
        desired=entry['desired_positions'];observed=entry['observed_positions']
        if len(desired)!=2 or len(observed)!=2 or observed[0]!=observed[1]:
            raise ValueError('Repeatable paired endpoint evidence required')
        rules[','.join(map(str,desired))]={
            'desired_positions':deepcopy(desired),
            'required_current_goals':deepcopy(lower['command_goals']),
            'required_current_positions':deepcopy(lower['expected_positions']),
            'command_goals':deepcopy(entry['command_goals']),
            'expected_positions':deepcopy(observed[0]),
            'maximum_observed_error_counts':max(entry['candidate_errors_counts']),
        }
    if set(rules)!= {'2387,1727','2389,1725'}:
        raise ValueError('Unexpected endpoint lookup domain')
    return {
        'schema':'rocell.local_pair_endpoint_policy.v1',
        'scope':'TWO_DISCRETE_ENDPOINTS_FROM_VALIDATED_LOWER_PLATEAU',
        'anchor_policy_training_export':anchor_policy['training_export'],
        'anchor_policy_heldout_export':anchor_policy['heldout_export'],
        'lookup_analysis_export':lookup_analysis_export,
        'rules':rules,
        'fine_endpoint_lookup_validated':True,
        'local_interpolation_validated':False,
        'general_workspace_compensation_validated':False,
        'movement_authorized':False,
        'fresh_feedback_required':True,
        'automatic_retry':False,
        'automatic_return':False,
    }


def resolve_endpoint(policy,*,current_goals,current_positions,desired_positions):
    """Resolve a measured discrete endpoint only from its validated approach state."""
    if (policy.get('schema')!='rocell.local_pair_endpoint_policy.v1' or
            policy.get('fine_endpoint_lookup_validated') is not True or
            policy.get('local_interpolation_validated') is not False):
        raise ValueError('Validated discrete endpoint policy required')
    rule=policy['rules'].get(','.join(map(str,desired_positions)))
    if rule is None:
        raise ValueError('Desired endpoint is outside validated discrete lookup set')
    if list(current_goals)!=rule['required_current_goals']:
        raise ValueError('Current goals differ from validated lower conditioning state')
    if len(current_positions)!=2 or any(not lo<=value<=hi for value,lo,hi in zip(
            current_positions,rule['required_current_positions']['minimum'],
            rule['required_current_positions']['maximum'])):
        raise ValueError('Fresh position is outside validated lower plateau')
    return {
        'schema':'rocell.local_pair_endpoint_resolution.v1',
        'desired_positions':deepcopy(rule['desired_positions']),
        'command_goals':deepcopy(rule['command_goals']),
        'expected_positions':deepcopy(rule['expected_positions']),
        'maximum_observed_error_counts':rule['maximum_observed_error_counts'],
        'fresh_feedback_required':True,
        'movement_authorized':False,
        'automatic_retry':False,
        'automatic_return':False,
    }
