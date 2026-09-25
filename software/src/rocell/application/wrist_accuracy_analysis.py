"""Offline command quantization and response analysis; never compensation.

Models the SHA-pinned Waveshare reference, not an attested installed binary.
Original trial validation is mandatory before comparing retained measurements.
"""
import math

from .absolute_wrist_result_review import review_absolute_wrist_result
from .absolute_wrist_capture import validate_absolute_wrist_capture
from .wizard_diagnostic_coordinator import decode_diagnostic_json
from rocell.arm.telemetry_coverage import complete_frame_interval, iter_window_records

REFERENCE_SHA256 = 'a28247fee0bbb65cc034ff206031b8700d2b1ec8e3a1fa4b1a5a7365c55f1a57'
STEP_RAD = 2 * math.pi / 4096


def reference_wrist_goal(target_rad):
    """Mirror C++ round (ties away from zero), not Python's ties-to-even."""
    if type(target_rad) not in (int, float) or not math.isfinite(target_rad):
        raise ValueError('Finite radian target required')
    limited = min(math.pi/2, max(-math.pi/2, target_rad))
    steps = limited / STEP_RAD
    offset = int(math.copysign(math.floor(abs(steps)+.5), steps))
    # The pinned source commands around 2047 but decodes around 2048.
    # This is a reference prediction, never a compensating command offset.
    goal_register = 2047+offset
    represented = (goal_register-2048)*STEP_RAD
    return dict(requested_rad=target_rad, clamped_rad=limited,
        goal_register=goal_register, representable_rad=represented,
        quantization_error_deg=math.degrees(offset*STEP_RAD-limited),
        reference_feedback_error_deg=math.degrees(represented-target_rad),
        command_midpoint=2047, feedback_midpoint=2048,
        clamped=limited != target_rad)


def analyze_wrist_accuracy(request, raw, *, expected_basis):
    review = review_absolute_wrist_result(request, raw, expected_basis=expected_basis)
    trial = decode_diagnostic_json(raw, maximum=256*1024)
    post = trial['post']
    data = validate_absolute_wrist_capture(request, post, phase='post',
        command_completed_ns=trial['write']['finished_ns'])
    selected, windows, _ = complete_frame_interval(data, post['read_windows'])
    records = list(iter_window_records(selected, windows))
    result = dict(schema='rocell.wrist_accuracy_analysis.v2',
        basis=expected_basis, reference_source_sha256=REFERENCE_SHA256,
        installed_firmware_verified=False, trial_sha256=review['trial_sha256'],
        endpoint_status=review['endpoint']['status'],
        reference_goal=reference_wrist_goal(review['preview']['candidate_command']['rad']),
        status='INSUFFICIENT_EVIDENCE', final_reported_deg=None,
        final_error_to_representable_deg=None, final_error_to_goal_steps=None,
        load=None, motion_authorized=False, compensation_recommended=False)
    if review['capture_issues'] or not review['transport_clean'] or not records:
        return result
    final = records[-1]['fields']['t']
    goal = result['reference_goal']
    residual = final-goal['representable_rad']
    first = len(records)-1
    while first > 0 and records[first-1]['fields']['t'] == final:
        first -= 1
    tail = records[first:]
    # tT is a vendor load field, not calibrated torque. Missing remains missing.
    loads = [r['fields'].get('tT') for r in tail]
    valid = [v for v in loads if type(v) in (int, float) and math.isfinite(v)]
    result.update(status='REFERENCE_MODEL_COMPARISON', final_reported_deg=math.degrees(final),
        final_error_to_representable_deg=math.degrees(residual),
        final_error_to_goal_steps=residual/STEP_RAD,
        load=dict(field='tT', calibrated_torque=False, constant_position_frames=len(tail),
            observed_count=len(valid), missing_or_invalid_count=len(tail)-len(valid),
            minimum=min(valid) if valid else None, maximum=max(valid) if valid else None,
            last=loads[-1] if loads and type(loads[-1]) in (int,float) and math.isfinite(loads[-1]) else None,
            changed_during_constant_position=len(set(valid)) > 1))
    return result
