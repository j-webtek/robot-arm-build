"""Measured P2L to P2 wrist-only contract and sampled geometry review."""
import hashlib
from pathlib import Path

from rocell.geometry import UrdfModel
from .large_pose_ladder import STEP_RAD, _sample
from .large_pose_relief_record import assess_large_pose_relief_record, decode_large_pose_relief_record

SOURCE_POSITIONS = (2047,2291,1825,2844,1720,2041,2047)
SOURCE_GOALS = (2047,2283,1831,2842,1719,2040,2047)
TARGET_GOALS = (2047,2283,1831,2842,1785,2040,2047)


def review_p2_wrist(raw, *, expected_boot, model_path):
    assessment = assess_large_pose_relief_record(raw, expected_boot=expected_boot, profile='P2L')
    endpoint = decode_large_pose_relief_record(raw, profile='P2L')['endpoint'][-1]['joints']
    positions = tuple(j['position'] for j in endpoint)
    goals = tuple(j['goal'] for j in endpoint)
    if positions != SOURCE_POSITIONS or goals != SOURCE_GOALS:
        raise ValueError('Record differs from pinned measured P2L endpoint')
    path = Path(model_path).resolve()
    model = UrdfModel.from_file(path)
    base_angles = [-(positions[0]-2048)*STEP_RAD, (positions[1]-2048)*STEP_RAD,
                   (positions[3]-1024)*STEP_RAD, (positions[4]-2048)*STEP_RAD,
                   -(positions[5]-2048)*STEP_RAD]
    def sample(delta):
        angles = base_angles.copy()
        angles[3] += delta*STEP_RAD
        points, separation = _sample(model, angles)
        return points['hand_tcp'], separation-30
    # Sweep the entire allowed positive travel, not just an assumed perfect endpoint.
    envelope = [sample(delta/2) for delta in range(161)]
    nominal = sample(TARGET_GOALS[4]-SOURCE_GOALS[4])[0]
    return dict(schema='rocell.p2_wrist_review.v1', source_assessment=assessment,
        source_record_sha256=hashlib.sha256(raw).hexdigest(),
        model_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
        source_positions=list(positions), source_goals=list(goals), target_goals=list(TARGET_GOALS),
        selected_servo_ids=[15], command_delta_counts=66,
        absolute_target_minus_measured_position_counts=65,
        maximum_travel_counts=80, endpoint_tolerance_counts=12,
        passive_drift_limit_counts=2, source_tolerance_counts=3,
        speed=20, acceleration=1, maximum_write_attempts=1,
        start_tcp_mm=list(sample(0)[0]), nominal_tcp_mm=list(nominal),
        swept_minimum_tcp_z_mm=min(p[0][2] for p in envelope),
        swept_minimum_capsule_clearance_mm=min(p[1] for p in envelope),
        sweep_samples=len(envelope),
        assumptions=['Single logical wrist joint; shoulder and elbow held fixed',
                     'Nominal endpoint assumes previous +1-count wrist bias persists',
                     'Sweep covers 0..80 counts; not full multi-joint uncertainty',
                     'No cables, full meshes, attached tool or registered board',
                     'Discrete geometry samples are not a continuous collision proof'],
        hardware_access=False, movement_authorized=False, physical_clearance_verified=False,
        retry_allowed=False, return_allowed=False)
