"""Offline bounded target choices reconstructed from original telemetry bytes.

Neither historic pose nor its timestamps are current admission evidence. The
wizard must bind the retained source to its unit/session before attaching a draft.
"""
import math

from .observational_capture_preview import decode_historical_baseline
from rocell.motion.observational_wrist_plan import validated_wrist_baseline
from rocell.motion.absolute_wrist_diagnostic import TARGETS_DEG, draft_absolute_wrist, preview_absolute_wrist


def draft_choices_from_capture(observation):
    samples, captured_end, details = decode_historical_baseline(observation)
    baseline = validated_wrist_baseline(samples=samples, now_ns=captured_end)
    start = baseline[-1]['joints_rad']
    choices, held = [], []
    for target in TARGETS_DEG:
        direction = 1 if math.radians(target) > start['t'] else -1
        try:
            draft = draft_absolute_wrist(expected_start_joints_rad=start, target_deg=target, direction=direction)
            # Every selected frame must permit the same bounded approach, not
            # merely the final frame used to freeze the expected starting pose.
            preview_absolute_wrist(draft, samples=baseline, now_ns=captured_end)
        except ValueError as error:
            held.append(dict(target_deg=target, reason=str(error)))
            continue
        choices.append(dict(draft=draft.to_dict(), draft_sha256=draft.sha256))
    return dict(schema='rocell.absolute_wrist_capture_drafts.v1', **details,
        captured_end_ns=captured_end, choices=choices, held_targets=held,
        historical_only=True, fresh_owned_baseline_required=True,
        motion_authorized=False, physical_accuracy_verified=False)
