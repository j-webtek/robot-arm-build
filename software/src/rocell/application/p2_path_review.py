"""Offline timing-order comparison, not a physical-clearance certificate."""
import hashlib
from pathlib import Path

from rocell.geometry import UrdfModel
from rocell.application.large_pose_ladder import STEP_RAD, _sample
from rocell.application.large_pose_relief_record import (
    assess_large_pose_relief_record, decode_large_pose_relief_record,
)


def review_p2_path(raw, *, expected_boot, model_path, subdivisions=40):
    if type(subdivisions) is not int or not 2 <= subdivisions <= 200:
        raise ValueError('Invalid grid resolution')
    assessment = assess_large_pose_relief_record(raw, expected_boot=expected_boot)
    endpoint = decode_large_pose_relief_record(raw)['endpoint'][-1]['joints']
    positions = [joint['position'] for joint in endpoint]
    goals = [joint['goal'] for joint in endpoint]
    angles = (-(positions[0]-2048)*STEP_RAD, (positions[1]-2048)*STEP_RAD,
              (positions[3]-1024)*STEP_RAD, (positions[4]-2048)*STEP_RAD,
              -(positions[5]-2048)*STEP_RAD)
    path = Path(model_path).resolve()
    model = UrdfModel.from_file(path)

    def sample(shoulder, wrist):
        state = list(angles)
        state[1] -= 65*STEP_RAD*shoulder
        state[3] += 66*STEP_RAD*wrist
        points, separation = _sample(model, state)
        return points['hand_tcp'], separation-30.0

    fractions = [i/subdivisions for i in range(subdivisions+1)]
    def envelope(pairs):
        rows = [(s, w, *sample(s, w)) for s, w in pairs]
        lowest = min(rows, key=lambda row: row[2][2])
        return dict(sample_count=len(rows), minimum_tcp_z_mm=lowest[2][2],
                    minimum_capsule_clearance_mm=min(row[3] for row in rows),
                    lowest_progress=dict(shoulder=lowest[0], wrist=lowest[1]))

    start, _ = sample(0, 0)
    lifted, _ = sample(1, 0)
    finish, _ = sample(1, 1)
    intermediate = goals.copy()
    intermediate[1] -= 65
    intermediate[2] += 65
    target = intermediate.copy()
    target[4] += 66
    return dict(
        schema='rocell.p2_path_review.v1', source_assessment=assessment,
        source_record_sha256=hashlib.sha256(raw).hexdigest(),
        model_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
        source_positions=positions, source_goals=goals,
        proposed_p2l_goals=intermediate, proposed_p2_goals=target,
        start_tcp_mm=list(start), p2l_tcp_mm=list(lifted), p2_tcp_mm=list(finish),
        synchronous=envelope((t, t) for t in fractions),
        independent_progress=envelope((s, w) for s in fractions for w in fractions),
        shoulder_first=envelope([(t, 0) for t in fractions]+[(1, t) for t in fractions]),
        recommendation='P1 -> P2L shoulder pair only; reacquire before wrist step',
        assumptions=['Physical angle changes equal commanded goal deltas',
                     'Monotonic joint progress without overshoot',
                     'Shoulder pair modeled as one logical joint',
                     'Sampled grid is not a continuous collision proof',
                     'No cables, tool, full link meshes or registered board'],
        physical_clearance_verified=False, hardware_access=False,
        movement_authorized=False,
    )
