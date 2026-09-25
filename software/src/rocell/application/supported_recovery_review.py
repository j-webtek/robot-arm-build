"""Strict recovery-record replay. No device access, signing or motion authority.

The controller's authentication flag is an assertion, not independently verified
provenance. DEVICE_CAPTURE means reported acquisition, not external tip metrology.
Failed/incomplete recovery remains inconclusive; no retry or pair is authorized.
"""
import hashlib
from pathlib import Path

from .first_motion_contract import canonical
from .hold_bound_replay import _policy
from .hold_record_replay import _assess_hold
from .servo_diagnostic_contract import _identifier, _integer
from .servo_start_authorization import _hex
from .wizard_diagnostic_coordinator import decode_diagnostic_json
from .wizard_diagnostic_export import WizardDiagnosticExporter, verify_export


def recovery_policy(policy, *, profile='supported'):
    if profile not in ('supported','six_count'):
        raise ValueError('Reviewed recovery profile required')
    if (type(policy) is not dict or set(policy) !=
            {'schema', 'hold_policy', 'initial_residual_counts'} or
            policy['schema'] != f'rocell.{profile}_recovery_policy.v1'):
        raise ValueError('Exact recovery policy required')
    bound=6 if profile=='six_count' else 5
    _integer(policy['initial_residual_counts'], bound, bound)
    hold = policy['hold_policy']
    limits = _policy(hold)
    if hold['drift'] != 2 or hold['speed'] != 20 or hold['permit_explicit_enable'] != 0:
        raise ValueError('Recovery cannot change arrival tolerance or enable torque')
    return hold, limits


def assess_recovery(records, *, expected_plan, expected_policy, origin, profile='supported'):
    result = dict(schema=f'rocell.{profile}_recovery_review.v1', origin=origin,
        category='INCONCLUSIVE', progression_authority=False, whole_arm_ready=False,
        provenance_verified=False, physical_tip_accuracy_verified=False)
    try:
        if origin not in ('SIMULATION', 'DEVICE_CAPTURE'):
            raise ValueError('Explicit evidence origin required')
        hold, limits = recovery_policy(expected_policy,profile=profile)
        if (type(expected_plan) is not dict or set(expected_plan) !=
                {'schema', 'boot_id', 'command_id', 'origin', 'policy_sha256'} or
                expected_plan['schema'] != f'rocell.{profile}_recovery_plan.v1' or
                expected_plan['origin'] != 'DEVICE_CAPTURE'):
            raise ValueError('Recovery plan required')
        _hex(expected_plan['boot_id'], 16)
        _identifier(expected_plan['command_id'])
        policy_hash = hashlib.sha256(canonical(expected_policy)).hexdigest()
        plan_hash = hashlib.sha256(canonical(expected_plan)).hexdigest()
        if expected_plan['policy_sha256'] != policy_hash:
            raise ValueError('Independent policy mismatch')
        if type(records) is not list or not 2 <= len(records) <= 12:
            raise ValueError('Record budget')
        clean = []
        schemas = {f'rocell.{profile}_recovery_{name}.v1': f'rocell.hold_{name}.v1'
                   for name in ('authorization', 'snapshot', 'action', 'terminal')}
        for record in records:
            if (type(record) is not dict or record['boot_id'] != expected_plan['boot_id'] or
                    record['command_id'] != expected_plan['command_id'] or
                    record['plan_sha256'] != plan_hash or record['policy_sha256'] != policy_hash):
                raise ValueError('Mixed/unbound recovery evidence')
            converted = {k: v for k, v in record.items() if k not in ('plan_sha256', 'policy_sha256')}
            converted['schema'] = schemas[record['schema']]
            clean.append(converted)
        auth = clean.pop(0)
        if (set(auth) != {'schema', 'boot_id', 'command_id', 'authentication_verified', 'received_us', 'policy'} or
                auth['schema'] != 'rocell.hold_authorization.v1' or
                auth['authentication_verified'] is not True or
                canonical(auth['policy']) != canonical(expected_policy)):
            raise ValueError('Recovery authorization mismatch')
        _integer(auth['received_us'])
        first_start = clean[0]['reads'][0][3][1]
        _integer(first_start)
        if auth['received_us'] >= first_start:
            raise ValueError('Authorization must precede acquisition')
        assessed = _assess_hold(clean, allow_enable=False, limits=limits,
            maximum_pair_us=hold['pair_us'], maximum_gap_us=hold['maximum_gap_us'],
            windows=hold['joints'], include_endpoint=True, supported_recovery=True,
            recovery_limit=expected_policy['initial_residual_counts'])
        result.update(plan_sha256=plan_hash, policy_sha256=policy_hash)
        if assessed['category'] != 'SIMULATED_HOLD_VERIFIED':
            raise ValueError('Recovery replay failed')
        result.update(category=('SIMULATED_RECOVERY_VERIFIED' if origin == 'SIMULATION'
                                else 'CONTROLLER_REPORTED_RECOVERY_VERIFIED'),
            endpoint=assessed['endpoint'], action_count=assessed['action_count'],
            snapshot_count=assessed['snapshot_count'], target_count=assessed['target_count'])
    except (ValueError, KeyError, TypeError, IndexError, AttributeError):
        result['reason'] = 'INCOMPLETE_INVALID_OR_UNCERTAIN_RECOVERY_EVIDENCE'
    return result


def export_recovery(root, records, *, expected_plan, expected_policy, origin, profile='supported'):
    subject = dict(plan=expected_plan, policy=expected_policy, origin=origin)
    result = assess_recovery(records, expected_plan=expected_plan,
                             expected_policy=expected_policy, origin=origin,profile=profile)
    attachments = {'recovery-records.json': canonical(records),
                   'recovery-subject.json': canonical(subject),
                   'recovery-assessment.json': canonical(result)}
    if sum(map(len, attachments.values())) > 60000:
        raise ValueError('Recovery export budget exceeded')
    exporter = WizardDiagnosticExporter(Path(root))
    exporter.prepare(create=True)
    exported = exporter.export({'mode': 'supported-recovery-review'}, [], attachments=attachments)
    if replay_recovery(exported['path']) != result:
        raise ValueError('Recovery export replay mismatch')
    return exported


def replay_recovery(path):
    # The export verifier compares contained paths against an absolute root.
    # Normalize CLI-relative paths without weakening manifest/hash validation.
    path = Path(path).resolve()
    if not verify_export(path)['valid']:
        raise ValueError('Invalid recovery export manifest')
    def read(name):
        return decode_diagnostic_json((path / f'attachment-recovery-{name}.json').read_bytes(),
                                      maximum=60000)
    subject = read('subject')
    if type(subject) is not dict or set(subject) != {'plan', 'policy', 'origin'}:
        raise ValueError('Invalid recovery export subject')
    profiles={'rocell.supported_recovery_policy.v1':'supported',
              'rocell.six_count_recovery_policy.v1':'six_count'}
    profile=profiles.get(subject['policy'].get('schema'))
    if profile is None:raise ValueError('Unknown recovery replay profile')
    result = assess_recovery(read('records'), expected_plan=subject['plan'],
                             expected_policy=subject['policy'], origin=subject['origin'],profile=profile)
    if canonical(result) != canonical(read('assessment')):
        raise ValueError('Stored recovery assessment differs from replay')
    return result
