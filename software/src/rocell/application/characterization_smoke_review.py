"""Offline single-leg review; no signing, transport, or movement authority."""
from .characterization_reference import decode_reference


def review_smoke_reference(raw, *, reference_sha256, goals):
    """Keep target-register changes distinct from measured travel estimates.

    The installed smoke pattern changes the paired target registers by -8/+8.
    Existing residuals mean this is not necessarily an eight-count physical move.
    Neither encoder bounds nor these estimates establish external clearance.
    """
    reference = decode_reference(raw, expected_sha256=reference_sha256)
    joints = reference['poses'][-1]['joints']
    expected = [[joints[1]['goal'] - 8, joints[2]['goal'] + 8]]
    if goals != expected or any(type(v) is not int for row in goals for v in row):
        raise ValueError('Not the reviewed single-leg smoke target')
    if sum(goals[0]) != 4114 or any(not 0 <= v <= 4095 for v in goals[0]):
        raise ValueError('Invalid paired target')
    travel = [goals[0][i] - joints[i + 1]['position'] for i in range(2)]
    if not (-32 <= travel[0] <= -2 and 2 <= travel[1] <= 32):
        raise ValueError('Measured baseline does not support bounded intended travel')
    return dict(
        reference_sha256=reference_sha256,
        measured_positions=[j['position'] for j in joints],
        registered_goals=[j['goal'] for j in joints],
        position_minus_goal=[j['position'] - j['goal'] for j in joints],
        proposed_pair_targets=goals[0], target_register_deltas=[-8, 8],
        target_minus_measured=travel, movement_authorized=False,
        physical_clearance_verified=False, physical_accuracy_verified=False,
        fresh_admission_required=True,
    )
