"""Compare illustrative elbow paths against a replayed pose; never access hardware.

This is a planning report, not an admission receipt. The observed positions may
already be stale, and encoder bounds do not establish Cartesian clearance.
"""
import argparse
import json
from pathlib import Path

from rocell.application.pose_observation_export import replay_pose_observation


def candidate_paths(anchor, low=2893, high=2909):
    if type(anchor) is not int or not low <= anchor <= high:
        raise ValueError('Observed elbow anchor is outside the reviewed envelope')
    return [dict(offset_counts=offset, targets=[anchor + offset, anchor],
                 fits_encoder_envelope=low <= anchor + offset <= high)
            for offset in (-6, 6, 10, 12)]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pose-export', required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1] / 'runs/wizard-exports'
    replay = replay_pose_observation(root, args.pose_export)
    assessment = replay['assessment']
    if assessment['category'] != 'STABLE_SAMPLED_POSE':
        raise ValueError('Stable sampled evidence required for this planning comparison')
    elbow = next(j for j in assessment['joints'] if j['servo_id'] == 14)
    print(json.dumps(dict(
        source_export=args.pose_export, source_origin=assessment['origin'],
        source_sha256=replay['raw_bundle_sha256'],
        historical_anchor=elbow['last_position'], saved_goal=elbow['last_goal'],
        goal_residual_counts=elbow['last_goal'] - elbow['last_position'],
        encoder_envelope=[2893, 2909], paths=candidate_paths(elbow['last_position']),
        progression_authority=False, hardware_access=False,
        clearance_verified=False, proposed_policy_installed=False)))


if __name__ == '__main__':
    main()
