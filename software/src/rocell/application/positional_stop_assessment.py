"""Assess measured stop-test records for engineering review, never release.

Operator observations and referenced measurement originals must be independently
reviewed/authenticated before qualification. This pure calculation neither sends
stop commands nor asserts that a measured terminal state is mechanically safe.
"""
import hashlib
import math

from .first_motion_contract import canonical
from .wizard_diagnostic_coordinator import decode_diagnostic_json
from rocell.safety.positional_campaign_authority import PositionalCampaignIntent

SCHEMA = 'rocell.positional_stop_observations.v1'
FAULTS = ('operator_stop', 'feedback_loss', 'usb_loss', 'host_loss')
SCOPE_REFS = ('source_sha256', 'protocol_review_sha256', 'configuration_sha256',
    'workcell_sha256', 'tool_payload_sha256', 'native_controller_review_sha256')


def expected_scope(request):
    if type(request) is not PositionalCampaignIntent:
        raise ValueError('Exact campaign scope required')
    body = request.to_dict()
    return dict(usb_identity=body['usb_identity'],
        references={name: body['references'][name] for name in SCOPE_REFS},
        route_sha256=hashlib.sha256(canonical(body['legs'])).hexdigest())


def assess_stop_observations(request, raw):
    scope = expected_scope(request)
    value = decode_diagnostic_json(raw, maximum=131072)
    fields = {'schema', 'scope', 'basis', 'installed_behavior_basis', 'strategy',
        'limits', 'trials', 'gravity_load_review', 'safe_terminal_definition'}
    if (type(value) is not dict or set(value) != fields or canonical(value) != raw
            or value['schema'] != SCHEMA or value['basis'] != 'PHYSICAL_OBSERVATIONS'
            or value['scope'] != scope):
        raise ValueError('Exact scoped physical stop observation record required')
    holds = []
    def text(value):
        return type(value) is str and 1 <= len(value.strip()) <= 2048
    def number(value):
        return type(value) in (float, int) and math.isfinite(value) and value >= 0
    def digest(value):
        return type(value) is str and len(value) == 64 and all(c in '0123456789abcdef' for c in value) and value != '0'*64
    for name in ('installed_behavior_basis', 'strategy', 'gravity_load_review', 'safe_terminal_definition'):
        if not text(value[name]): holds.append(name + '_missing')
    limits = value['limits']
    if type(limits) is not dict or set(limits) != {'maximum_response_ms', 'maximum_residual_motion_rad'}:
        raise ValueError('Explicit reviewed stop-test limits required')
    for name, limit in limits.items():
        if not number(limit): raise ValueError('Finite nonnegative stop-test limits required')
    # Limits are supplied for engineering review; no arbitrary universal safe
    # latency/angle is invented by this software.
    trials = value['trials']
    if type(trials) is not list or len(trials) > 32:
        raise ValueError('Bounded stop trial list required')
    seen = set()
    results = []
    required = {'fault', 'fault_observed_ns', 'motion_ceased_ns', 'residual_motion_rad',
        'measurement_original_sha256', 'terminal_state_observed', 'independent_of_host_usb'}
    for trial in trials:
        if type(trial) is not dict or set(trial) != required or trial['fault'] not in FAULTS:
            raise ValueError('Exact known stop trial fields required')
        fault = trial['fault']
        seen.add(fault)
        issues = []
        start, end = trial['fault_observed_ns'], trial['motion_ceased_ns']
        timing = (type(start) is int and type(end) is int and 0 < start <= end < 2**63)
        response = (end-start)/1e6 if timing else None
        if not timing: issues.append('measured_stop_timing_missing')
        elif response > limits['maximum_response_ms']: issues.append('response_limit_exceeded')
        residual = trial['residual_motion_rad']
        if not number(residual): issues.append('measured_residual_motion_missing')
        elif residual > limits['maximum_residual_motion_rad']: issues.append('residual_motion_limit_exceeded')
        if not digest(trial['measurement_original_sha256']): issues.append('measurement_original_missing')
        if not text(trial['terminal_state_observed']): issues.append('terminal_observation_missing')
        if type(trial['independent_of_host_usb']) is not bool:
            raise ValueError('Explicit independence observation required')
        if fault in ('usb_loss', 'host_loss') and trial['independent_of_host_usb'] is not True:
            issues.append('independent_protective_response_missing')
        results.append(dict(fault=fault, response_ms=response, issues=issues))
    for fault in FAULTS:
        if fault not in seen: holds.append('missing_trial_' + fault)
    if any(row['issues'] for row in results): holds.append('trial_evidence_incomplete_or_outside_limits')
    return dict(schema='rocell.positional_stop_assessment.v1',
        observations_sha256=hashlib.sha256(raw).hexdigest(), scope=scope,
        status='HELD' if holds else 'READY_FOR_ENGINEERING_REVIEW', holds=holds, trials=results,
        measurement_originals_verified=False, reviewer_identity_authenticated=False,
        physical_stop_verified=False, motion_authorized=False, unattended_release=False)
