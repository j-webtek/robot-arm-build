"""Offline +12-count experiment review; never authorizes or sends movement.

Use an independently replayed ordinary-hold pair preparation. This experiment
checks the actual A -> A+12 -> A path, not an unused A-12 target. Live admission
still needs installed settings, same-boot hold, approval and native fresh checks.
"""
import hashlib

from .first_motion_contract import canonical
from .held_pair_settings import encode_pair_settings, require_pair_settings_match
from .r10_provisioned_evidence import POLICY

FORWARD = 'elbow-plus12-forward'
RETURN = 'elbow-plus12-return'


def review_export(export_root, preparation_id):
    """Public entry point: independently replay source evidence before review."""
    from .held_pair_preparation import replay_held_pair_preparation
    replay = replay_held_pair_preparation(export_root, preparation_id)
    result = review_preparation(replay['preparation'])
    return dict(result, preparation_export_id=preparation_id,
                preparation_sha256=replay['preparation_sha256'])


def settings_bytes():
    return encode_pair_settings(forward_command_id=FORWARD,
        return_command_id=RETURN, offset_counts=12, tolerance_counts=2)


def review_preparation(preparation):
    """Check reviewed policy and illustrative bounds; do not infer fresh pose."""
    policy = preparation['policy']
    config = dict(schema='rocell.controller_hold.v1',
        command_id='r7-supported-hold-20260918', start_port=8081, hold_policy=policy)
    if hashlib.sha256(canonical(config)).hexdigest() != POLICY:
        raise ValueError('Experiment must retain the reviewed hold policy')
    settings_hash = require_pair_settings_match(settings_bytes(), preparation)
    anchor = preparation['historical_anchor']
    if type(anchor) is not int:
        raise ValueError('Integer encoder anchor required')
    low, high = policy['joints'][3]
    targets = [anchor + 12, anchor]
    eligible = low <= anchor <= high and low <= targets[0] <= high
    return dict(schema='rocell.elbow_displacement_review.v1',
        category='ILLUSTRATIVE_PATH_FITS' if eligible else 'NOT_ELIGIBLE',
        historical_anchor=anchor, illustrative_targets=targets, envelope=[low, high],
        settings_sha256=settings_hash, fresh_same_boot_handoff_required=True,
        installed_settings_receipt_required=True, maximum_position_commands=2,
        verified_export_before_return_required=True, progression_authority=False,
        physical_tip_accuracy_verified=False, retry_allowed=False)
