"""Non-authoritative count-space trial draft from a replayed hold export."""
from pathlib import Path

from .hold_observed_review import replay_hold_observation
from .hold_started_review import _prepared
from .product_ghost_export_review import _read


def draft_held_elbow_trial(root, export_id, *, offset_counts=6, tolerance_counts=2):
    """No hardware access or command token. Historical targets are illustrative.

    A future native session must establish a new fresh held anchor. This draft
    cannot authorize that session or turn saved evidence into a live baseline.
    """
    if (type(offset_counts) is not int or not 1 <= abs(offset_counts) <= 16 or
            type(tolerance_counts) is not int or not 0 <= tolerance_counts <= 2 or
            abs(offset_counts) <= 2*tolerance_counts):
        raise ValueError('Bounded displacement with nonoverlapping endpoint bands required')
    root = Path(root).resolve()
    replay = replay_hold_observation(root, export_id)
    assessment = replay['assessment']
    if (assessment['category'] != 'CONTROLLER_REPORTED_HOLD_VERIFIED' or
            replay['stable_status_observed'] is not True):
        raise ValueError('Replay-verified complete hold reference required')
    endpoint = assessment['endpoint']
    if endpoint['torque_settled'] != 1 or endpoint['servo_id'] != 14:
        raise ValueError('Held elbow reference required')
    link, source_digest = _read(root, export_id, 'attachment-observed-hold.json')
    _, _, _, policy, _ = _prepared(root, link['prepared_export_id'])
    anchor = endpoint['settled_position']
    low, high = policy['joints'][3]
    if not (low <= anchor <= high and low <= anchor+offset_counts <= high):
        raise ValueError('Illustrative targets outside reviewed hold envelope')
    return dict(schema='rocell.held_elbow_trial_draft.v1', source_export_id=export_id,
        source_sha256=source_digest, source_boot_id=assessment['boot_id'],
        origin='OFFLINE_PROPOSAL', unit='servo_count', servo_id=14,
        historical_anchor=anchor, illustrative_targets=[anchor+offset_counts, anchor],
        offsets_from_fresh_anchor=[offset_counts, 0], tolerance_counts=tolerance_counts,
        envelope=[low, high], speed=20, acceleration=1,
        fresh_held_anchor_required=True, verified_export_before_return_required=True,
        progression_authority=False, retry_allowed=False, physical_tip_accuracy_verified=False)
