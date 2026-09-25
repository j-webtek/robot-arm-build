"""Exact observed-pose recovery contract; no network, keys loaded, or device I/O.

Reuse the existing six-count wire schema with a distinct command and policy hash.
This is not a live runner: installation/startup receipt admission remains separate.
"""
import hashlib

from .first_motion_contract import canonical
from .observed_pose_candidate import replay_candidate
from .supported_recovery_start import freeze_recovery_plan, sign_recovery

COMMAND = 'observed-pose-six-count-recovery-v1'
HOLD_SHA = 'cb844a0818b501f9186cf4e421628d28ea4c3e8c583e2171d6d15f62a0dc4354'
PAIR_SHA = '0dade56675bc9767358888d78c34258121f65e3eae7f92b95ed5b77cfc5b2835'


def recovery_policy_from_candidate(software_root, candidate_export):
    replay = replay_candidate(software_root, candidate_export)
    report = replay['report']
    if (hashlib.sha256(canonical(report['hold_settings'])).hexdigest() != HOLD_SHA or
            hashlib.sha256(canonical(report['pair_settings'])).hexdigest() != PAIR_SHA):
        raise ValueError('Exact observed-pose settings required')
    return dict(schema='rocell.six_count_recovery_policy.v1',
                hold_policy=report['hold_settings']['hold_policy'], initial_residual_counts=6)


def freeze_observed_recovery(software_root, candidate_export, *, boot_id):
    policy = recovery_policy_from_candidate(software_root, candidate_export)
    return freeze_recovery_plan(policy, boot_id=boot_id, command_id=COMMAND, profile='six_count')


def sign_observed_recovery(software_root, candidate_export, plan, challenge, key):
    """Caller must first verify deployment/startup and one-shot approval.

    This pure signing function cannot supply that authority. It refuses a frozen
    plan with any different command, policy, or boot, including legacy recovery.
    """
    policy = recovery_policy_from_candidate(software_root, candidate_export)
    expected = freeze_recovery_plan(policy, boot_id=challenge['boot_id'],
                                    command_id=COMMAND, profile='six_count')
    if plan != expected:
        raise ValueError('Observed recovery command/policy/boot mismatch')
    return sign_recovery(plan, challenge, key, approved_policy=policy, profile='six_count')
