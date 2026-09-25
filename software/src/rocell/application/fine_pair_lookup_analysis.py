"""Validate r50 fine-endpoint evidence without granting movement authority."""
from __future__ import annotations

from .fine_pair_lookup_validation import plan_fine_lookup_validation


def _error(actual, desired):
    return max(abs(a-b) for a,b in zip(actual,desired))


def analyze_fine_pair_lookup(result, *, source_export):
    """Apply the frozen r50 release rule to a completed result export."""
    plan=plan_fine_lookup_validation()
    if result.get('schema')!='rocell.fine_pair_lookup_result.v1':
        raise ValueError('Unexpected fine lookup result schema')
    if result.get('plan_sha256')!=plan['plan_sha256']:
        raise ValueError('Fine lookup result is not bound to the frozen plan')
    rows=result.get('rows')
    if type(rows) is not list or len(rows)!=plan['manifest']['legs']:
        raise ValueError('Incomplete fine lookup result')
    expected_goals=plan['manifest']['goals']
    for index,(row,target) in enumerate(zip(rows,expected_goals)):
        if row.get('leg')!=index or row.get('target')!=target:
            raise ValueError('Fine lookup result order or target differs')
        if type(row.get('actual')) is not list or len(row['actual'])!=2:
            raise ValueError('Fine lookup endpoint missing')

    entries=[]
    for comparison in plan['comparisons']:
        candidate_indices=(comparison['candidate_leg'],comparison['heldout_leg'])
        actuals=[rows[index]['actual'] for index in candidate_indices]
        desired=comparison['desired_positions']
        candidate_errors=[_error(actual,desired) for actual in actuals]
        direct_error=_error(comparison['retained_direct_control_actual'],desired)
        repeatable=actuals[0]==actuals[1]
        within_tolerance=max(candidate_errors)<=plan['release_rule'][
            'maximum_candidate_endpoint_error_counts']
        improves=max(candidate_errors)<direct_error
        entries.append({
            'desired_positions':desired,
            'command_goals':comparison['candidate_goals'],
            'observed_positions':actuals,
            'candidate_errors_counts':candidate_errors,
            'retained_direct_error_counts':direct_error,
            'exact_repeat':repeatable,
            'within_tolerance':within_tolerance,
            'improves_over_retained_direct':improves,
            'validated':repeatable and within_tolerance and improves,
        })
    validated=all(entry['validated'] for entry in entries)
    return {
        'schema':'rocell.fine_pair_lookup_analysis.v1',
        'source_export':source_export,
        'source_plan_sha256':plan['plan_sha256'],
        'entries':entries,
        'fine_endpoint_lookup_validated':validated,
        'general_compensation_validated':False,
        'cartesian_accuracy_validated':False,
        'stylus_accuracy_validated':False,
        'movement_authorized':False,
        'release_scope':'two_local_encoder_endpoint_lookups_only' if validated else 'none',
    }
