"""Offline proposal after the recorded r27 partial shoulder rise.

This is not a hardware admission decision. Preserve the last commanded pair
relationship instead of recentering each servo independently on its load error.
The nominal endpoint model omits link/cable collisions and board registration.
"""
import math

from .firmware_reference import forward, REFERENCE_SHA256


def preview_recovery(positions, goals):
    """Propose one additional 24-count mirrored target change, offline only."""
    reference = (2047, 2448, 1667, 2905, 1589, 2040, 2047)
    expected_goals = (2047, 2443, 1671, 2907, 1589, 2040, 2047)
    for values in (positions, goals):
        if (type(values) not in (tuple, list) or len(values) != 7
                or any(type(v) is not int or not 0 <= v <= 4095 for v in values)):
            raise ValueError('Seven integer encoder counts required')
    if tuple(goals) != expected_goals or any(abs(p-r) > 2 for p, r in zip(positions, reference)):
        raise ValueError('Not the reviewed local partial-arrival state')
    # Known residual envelope is an explicit recovery input, not a relaxed
    # arrival criterion. Wrong-side or larger errors require a new review.
    residuals = (positions[1]-goals[1], goals[2]-positions[2])
    if any(not 2 <= v <= 7 for v in residuals):
        raise ValueError('Residual outside recorded direction/envelope')
    targets = list(goals)
    targets[1] -= 24
    targets[2] += 24
    changes = (targets[1]-positions[1], targets[2]-positions[2])
    if not (-32 <= changes[0] < 0 < changes[1] <= 32):
        raise ValueError('Recovery exceeds bounded actual-position travel')
    step = 2*math.pi/4096
    def endpoint(shoulder_count):
        return forward((2048-positions[0])*step, (shoulder_count-2048)*step,
                       (positions[3]-1024)*step, (positions[4]-2048)*step)
    samples = [endpoint(count) for count in range(positions[1], targets[1]-1, -1)]
    increments = [b[2]-a[2] for a, b in zip(samples, samples[1:])]
    if not increments or min(increments) <= 0:
        raise ValueError('Nominal endpoint path does not consistently rise')
    return dict(schema='rocell.shoulder_clearance_recovery_preview.v1',
        reference_sha256=REFERENCE_SHA256, positions=list(positions), previous_goals=list(goals),
        proposed_goals=targets, selected_servo_ids=[12, 13],
        target_change_counts=[-24, 24], actual_to_target_counts=list(changes),
        preserved_commanded_pair_sum=goals[1]+goals[2],
        sample_count=len(samples), nominal_endpoint_rise_mm=samples[-1][2]-samples[0][2],
        minimum_nominal_increment_mm=min(increments),
        speed_counts_per_second=20, acceleration=1,
        requires_fresh_stationary_enabled_seven_joint_capture=True,
        requires_new_native_recovery_contract=True, hardware_access=False,
        movement_authorized=False, physical_clearance_verified=False,
        compensation_applied=False,
        limitations=['Historical input is not current state',
            'Nominal end edge is not the lowest gripper point',
            'No board registration, collision volumes, cable or contact model',
            'Follower-servo mechanical alignment is not established by this FK',
            'Existing r27 fault and baseline requirements prohibit live execution'])
