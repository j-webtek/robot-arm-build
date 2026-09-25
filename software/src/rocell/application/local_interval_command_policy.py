"""Compose discrete endpoint evidence with bounded upper-interval interpolation.

The policy translates a desired *measured encoder endpoint* into the command pair
supported by the r51 fit.  It never grants motion authority and never extrapolates.
"""
from __future__ import annotations

from copy import deepcopy

from .local_pair_endpoint_policy import resolve_endpoint


def derive_interval_command_policy(endpoint_policy,interval_model,*,model_export):
    """Build a fail-closed resolver from the validated r50 and r51 artifacts."""
    if (endpoint_policy.get('schema')!='rocell.local_pair_endpoint_policy.v1' or
            endpoint_policy.get('fine_endpoint_lookup_validated') is not True or
            endpoint_policy.get('movement_authorized') is not False):
        raise ValueError('Validated non-authorizing endpoint policy required')
    if (interval_model.get('schema')!='rocell.local_interval_model.v1' or
            interval_model.get('local_interval_interpolation_validated') is not False or
            interval_model.get('movement_authorized') is not False):
        raise ValueError('Rejected full-span model with bounded subinterval required')
    sub=interval_model.get('validated_subinterval',{})
    if (sub.get('minimum_command')!=2385 or sub.get('maximum_command')!=2389 or
            sub.get('training_commands')!=[2385,2389] or
            sub.get('heldout_commands')!=[2388] or
            sub.get('training_monotonic') is not True or
            sub.get('interpolation_validated') is not True or
            sub.get('extrapolation_allowed') is not False or
            sub.get('heldout_maximum_paired_error_counts',float('inf'))>2 or
            sub.get('heldout_p95_paired_error_counts',float('inf'))>2):
        raise ValueError('Validated 2385..2389 subinterval required')
    centers={row['command_goals'][0]:row['observed_position_center']
             for row in interval_model.get('centers',[])}
    if centers.get(2385)!=[2387,1728] or centers.get(2389)!=[2391,1724]:
        raise ValueError('Unexpected upper interval anchors')
    return {
        'schema':'rocell.local_interval_command_policy.v1',
        'scope':'DISCRETE_ENDPOINTS_PLUS_UPPER_2385_2389_INTERPOLATION',
        'endpoint_policy':deepcopy(endpoint_policy),
        'interval_model_export':model_export,
        'interval':{
            'minimum_command':2385,'maximum_command':2389,
            'minimum_observed_positions':[2387,1728],
            'maximum_observed_positions':[2391,1724],
            'maximum_heldout_error_counts':sub['heldout_maximum_paired_error_counts'],
            'required_current_goals':[2377,1737],
            'required_current_positions':{'minimum':[2385,1730],
                                          'maximum':[2386,1730]},
            'extrapolation_allowed':False,
        },
        'full_interval_interpolation_validated':False,
        'upper_interval_interpolation_validated':True,
        'fresh_feedback_required':True,
        'movement_authorized':False,
        'automatic_retry':False,
        'automatic_return':False,
    }


def _require_conditioned_start(interval,current_goals,current_positions):
    if list(current_goals)!=interval['required_current_goals']:
        raise ValueError('Current goals differ from validated lower conditioning state')
    bounds=interval['required_current_positions']
    if len(current_positions)!=2 or any(not lo<=value<=hi for value,lo,hi in zip(
            current_positions,bounds['minimum'],bounds['maximum'])):
        raise ValueError('Fresh position is outside validated lower plateau')


def resolve_interval_endpoint(policy,*,current_goals,current_positions,desired_positions):
    """Resolve a discrete endpoint or an in-domain interpolated encoder endpoint."""
    if (policy.get('schema')!='rocell.local_interval_command_policy.v1' or
            policy.get('upper_interval_interpolation_validated') is not True or
            policy.get('full_interval_interpolation_validated') is not False or
            policy.get('movement_authorized') is not False):
        raise ValueError('Validated non-authorizing interval policy required')

    # Preserve the two r50 endpoints exactly, including their original approach gates.
    key=','.join(map(str,desired_positions))
    if key in policy['endpoint_policy']['rules']:
        result=resolve_endpoint(policy['endpoint_policy'],current_goals=current_goals,
                                current_positions=current_positions,
                                desired_positions=desired_positions)
        return dict(result,resolution_mode='DISCRETE_VALIDATED_ENDPOINT')

    interval=policy['interval'];_require_conditioned_start(
        interval,current_goals,current_positions)
    if type(desired_positions) is not list or len(desired_positions)!=2:
        raise ValueError('Two desired encoder positions required')
    primary,paired=desired_positions
    minimum=interval['minimum_observed_positions'][0]
    maximum=interval['maximum_observed_positions'][0]
    if type(primary) is not int or type(paired) is not int or not minimum<=primary<=maximum:
        raise ValueError('Desired endpoint is outside validated observed interval')
    # The measured upper-interval centers lie on this paired-register manifold.
    if paired!=4115-primary:
        raise ValueError('Desired pair is outside validated observed manifold')
    command_primary=2385+(primary-minimum)
    if not interval['minimum_command']<=command_primary<=interval['maximum_command']:
        raise ValueError('Interpolated command would extrapolate')
    return {
        'schema':'rocell.local_pair_endpoint_resolution.v1',
        'resolution_mode':'UPPER_INTERVAL_INTERPOLATION',
        'desired_positions':deepcopy(desired_positions),
        'command_goals':[command_primary,4114-command_primary],
        'expected_positions':deepcopy(desired_positions),
        'maximum_observed_error_counts':interval['maximum_heldout_error_counts'],
        'domain':{'minimum_command':interval['minimum_command'],
                  'maximum_command':interval['maximum_command'],
                  'extrapolation_allowed':False},
        'fresh_feedback_required':True,
        'movement_authorized':False,
        'automatic_retry':False,
        'automatic_return':False,
    }
