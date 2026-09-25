"""Replay hash-bound native test sessions against an independently supplied plan.

Authentication_verified in a record is a controller assertion, not independently
verified device provenance. This entry point labels all results SIMULATION and
does not confer permission to operate hardware.
"""
import hashlib
import json
from pathlib import Path

from .first_motion_contract import canonical
from .hold_initialization_model import Limits
from .hold_record_replay import _assess_hold
from .servo_diagnostic_contract import _identifier, _integer
from .wizard_diagnostic_export import WizardDiagnosticExporter, verify_export


def _policy(policy):
    fields = {'schema', 'servo_id', 'joints', 'acceleration', 'age_us', 'baseline_gap_us',
              'deadline_us', 'drift', 'maximum_gap_us', 'pair_us', 'permit_explicit_enable',
              'scan_us', 'settle_us', 'speed'}
    if type(policy) is not dict or set(policy) != fields:
        raise ValueError('Exact policy fields required')
    if policy['schema'] != 'rocell.hold_policy.v1':
        raise ValueError('Policy schema')
    bounds = {'servo_id': (14, 14), 'acceleration': (1, 1), 'age_us': (1, 1000000),
              'baseline_gap_us': (1, 1000000), 'deadline_us': (1, 10000000),
              'drift': (0, 8), 'maximum_gap_us': (1, 1000000), 'pair_us': (1, 100000),
              'permit_explicit_enable': (0, 1), 'scan_us': (1, 1000000),
              'settle_us': (1, 1000000), 'speed': (1, 40)}
    for name, (low, high) in bounds.items():
        _integer(policy[name], low, high)
    if max(policy['baseline_gap_us'], policy['settle_us']) > policy['maximum_gap_us']:
        raise ValueError('Inconsistent timing policy')
    if type(policy['joints']) is not list or len(policy['joints']) != 7:
        raise ValueError('Seven joint windows required')
    for window in policy['joints']:
        if type(window) is not list or len(window) != 2:
            raise ValueError('Joint window shape')
        _integer(window[0], 0, 4095)
        _integer(window[1], window[0], 4095)
    return Limits(max_age_us=policy['age_us'], max_scan_us=policy['scan_us'],
                  min_baseline_gap_us=policy['baseline_gap_us'], settle_us=policy['settle_us'],
                  deadline_us=policy['deadline_us'], drift_counts=policy['drift'],
                  speed=policy['speed'], acceleration=policy['acceleration'])


def assess_bound_simulation(records, *, expected_plan, expected_policy, include_endpoint=False):
    result = dict(schema='rocell.bound_hold_replay.v1', origin='SIMULATION',
                  category='INCONCLUSIVE', progression_authority=False,
                  whole_arm_ready=False, provenance_verified=False)
    try:
        limits = _policy(expected_policy)
        if (type(expected_plan) is not dict or set(expected_plan) !=
                {'schema', 'boot_id', 'command_id', 'origin', 'policy_sha256'} or
                expected_plan['schema'] != 'rocell.hold_plan.v1' or
                expected_plan['origin'] != 'DEVICE_CAPTURE'):
            raise ValueError('Exact admitted plan required')
        boot = _identifier(expected_plan['boot_id'])
        if len(boot) != 32 or len(bytes.fromhex(boot)) != 16 or boot != boot.lower():
            raise ValueError('Boot identifier')
        command = _identifier(expected_plan['command_id'])
        policy_hash = hashlib.sha256(canonical(expected_policy)).hexdigest()
        if expected_plan['policy_sha256'] != policy_hash:
            raise ValueError('Independent policy hash mismatch')
        plan_hash = hashlib.sha256(canonical(expected_plan)).hexdigest()
        if type(records) is not list or not 2 <= len(records) <= 12:
            raise ValueError('Record budget')
        clean = []
        for record in records:
            if (type(record) is not dict or record['boot_id'] != boot or record['command_id'] != command or
                    record['plan_sha256'] != plan_hash or record['policy_sha256'] != policy_hash):
                raise ValueError('Unbound or mixed evidence')
            clean.append({k: v for k, v in record.items() if k not in ('plan_sha256', 'policy_sha256')})
        auth = clean.pop(0)
        if (set(auth) != {'schema', 'boot_id', 'command_id', 'authentication_verified', 'received_us', 'policy'} or
                auth['schema'] != 'rocell.hold_authorization.v1' or auth['authentication_verified'] is not True or
                canonical(auth['policy']) != canonical(expected_policy)):
            raise ValueError('Authorization record mismatch')
        _integer(auth['received_us'])
        first_start = clean[0]['reads'][0][3][1]
        _integer(first_start)
        if auth['received_us'] >= first_start:
            raise ValueError('Authorization must precede acquisition')
        assessment = _assess_hold(clean, allow_enable=bool(expected_policy['permit_explicit_enable']),
            limits=limits, maximum_pair_us=expected_policy['pair_us'],
            maximum_gap_us=expected_policy['maximum_gap_us'], windows=expected_policy['joints'],
            include_endpoint=include_endpoint)
        result.update(assessment)
        result['schema'] = 'rocell.bound_hold_replay.v1'
        result.update(plan_sha256=plan_hash, policy_sha256=policy_hash)
    except (ValueError, KeyError, TypeError, IndexError, AttributeError):
        result['reason'] = 'INVALID_BOUND_HOLD_EVIDENCE'
    if include_endpoint:
        result['schema'] = 'rocell.bound_hold_endpoint_review.v1'
    return result


def export_bound_simulation(root, records, *, expected_plan, expected_policy):
    result = assess_bound_simulation(records, expected_plan=expected_plan, expected_policy=expected_policy)
    attachments = {'hold-records.json': canonical(records), 'hold-plan.json': canonical(expected_plan),
                   'hold-policy.json': canonical(expected_policy), 'hold-assessment.json': canonical(result)}
    attachments['hold-endpoints.json'] = canonical(assess_bound_simulation(records,
        expected_plan=expected_plan, expected_policy=expected_policy, include_endpoint=True))
    if sum(map(len, attachments.values())) > 60000:
        raise ValueError('Bound hold export exceeds budget')
    exporter = WizardDiagnosticExporter(Path(root))
    exporter.prepare(create=True)
    exported = exporter.export({'mode': 'bound-hold-simulation'}, [], attachments=attachments)
    if replay_bound_simulation_export(exported['path']) != result:
        raise ValueError('Bound hold export replay mismatch')
    return exported


def replay_bound_simulation_export(path):
    path = Path(path)
    if not verify_export(path)['valid']:
        raise ValueError('Invalid bound hold export')
    def read(name):
        payload = (path / ('attachment-' + name + '.json')).read_bytes()
        if len(payload) > 131072:
            raise ValueError('Replay attachment exceeds budget')
        return json.loads(payload)
    result = assess_bound_simulation(read('hold-records'), expected_plan=read('hold-plan'),
                                     expected_policy=read('hold-policy'))
    if canonical(result) != canonical(read('hold-assessment')):
        raise ValueError('Bound hold assessment mismatch')
    if (path / 'attachment-hold-endpoints.json').exists():
        endpoints = assess_bound_simulation(read('hold-records'), expected_plan=read('hold-plan'),
                                            expected_policy=read('hold-policy'), include_endpoint=True)
        if canonical(endpoints) != canonical(read('hold-endpoints')):
            raise ValueError('Bound hold endpoint review mismatch')
    return result
