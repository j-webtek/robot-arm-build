"""Offline finite wrist campaign from verified P4; no motion transport."""
import hashlib
from pathlib import Path

from rocell.geometry import UrdfModel
from .large_pose_ladder import STEP_RAD, _sample
from .large_pose_relief_record import assess_large_pose_relief_record, decode_large_pose_relief_record

MODEL_SHA = 'a565718e7d74b07702802cf41eb9549a6e38e50b5e80aa9b887ab1ae3d0d8190'
POSITIONS = (2047,2225,1890,2716,1977,2041,2047)
GOALS = (2047,2217,1897,2711,1980,2040,2047)
TARGETS = (1915,1947,1980,1947,1915,1980)*2


def review_p4_repeat_campaign(raw, *, expected_boot, model_path):
    assessment = assess_large_pose_relief_record(raw, expected_boot=expected_boot, profile='P4')
    endpoint = decode_large_pose_relief_record(raw, profile='P4')['endpoint'][-1]['joints']
    if tuple(j['position'] for j in endpoint) != POSITIONS or tuple(j['goal'] for j in endpoint) != GOALS:
        raise ValueError('Source differs from retained P4 endpoint')
    path = Path(model_path).resolve()
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest != MODEL_SHA:
        raise ValueError('Kinematic model differs from reviewed model')
    model = UrdfModel.from_file(path)
    legs = []
    previous = GOALS[4]
    for number, target in enumerate(TARGETS, 1):
        goals = list(GOALS)
        goals[4] = target
        legs.append(dict(number=number, target_goals=goals, selected_servo_ids=[15],
            command_delta_counts=target-previous, direction=1 if target>previous else -1,
            target_wrist=target, speed=20, acceleration=1,
            maximum_write_attempts=1, requires_previous_export_receipt=number>1))
        previous = target
    # At each later leg, source must be within 12 counts of its preceding
    # verified goal. Sweep the full union of +/-80-count directional travel,
    # including the one-count opposite-direction allowance and first baseline.
    lows, highs = [], []
    previous = GOALS[4]
    for number, target in enumerate(TARGETS):
        lo, hi = (POSITIONS[4]-3, POSITIONS[4]+3) if number==0 else (previous-12, previous+12)
        lows.append(lo-80 if target<previous else lo-1)
        highs.append(hi+80 if target>previous else hi+1)
        previous = target
    low, high = min(lows), max(highs)
    samples = []
    for half_count in range(low*2, high*2+1):
        angles = [-(POSITIONS[0]-2048)*STEP_RAD, (POSITIONS[1]-2048)*STEP_RAD,
                  (POSITIONS[3]-1024)*STEP_RAD, (half_count/2-2048)*STEP_RAD,
                  -(POSITIONS[5]-2048)*STEP_RAD]
        points, separation = _sample(model, angles)
        samples.append((points['hand_tcp'][2], separation-30))
    return dict(schema='rocell.p4_repeat_campaign_review.v1', source_assessment=assessment,
        source_record_sha256=hashlib.sha256(raw).hexdigest(), model_sha256=digest,
        source_positions=list(POSITIONS), source_goals=list(GOALS), legs=legs,
        maximum_writes=len(legs), maximum_command_delta_counts=max(abs(l['command_delta_counts']) for l in legs),
        wrist_sweep_counts=[low, high], sweep_samples=len(samples),
        minimum_model_tcp_z_mm=min(z for z,_ in samples),
        minimum_model_capsule_clearance_mm=min(c for _,c in samples),
        midpoint_goal=1947, midpoint_arrivals_per_direction=2,
        proposed_endpoint_tolerance_counts=12, proposed_travel_limit_counts=80,
        proposed_global_passive_drift_limit_counts=2,
        required_controls=['Fresh three-snapshot starting pose, not retained pose alone',
            'One exclusive finite-campaign owner; fixed reviewed goals only',
            'Fresh prewrite position within one count of preceding stable endpoint',
            'Verify goal readback, fresh position direction, endpoint error and stability',
            'Bound passive drift against campaign baseline, not cumulatively per leg',
            'Export raw evidence and receive durable receipt before every next leg',
            'Stop on uncertain delivery, invalid feedback, drift, timeout or export failure',
            'No retry or automatic recovery; final goal is not a guaranteed return'],
        analysis_metrics=['Signed endpoint error grouped by goal and approach direction',
            'Within-direction endpoint spread across the two cycles',
            'Difference between midpoint arrivals from low and high directions',
            'Passive drift, capture timing and all failed legs retained'],
        hardware_access=False, movement_authorized=False, compensation_applied=False,
        native_campaign_implemented=False, physical_clearance_verified=False,
        limitations=['Fixed passive logical angles; full multi-joint uncertainty not swept',
            'No cables, full meshes, mounted tool or registered board',
            'Discrete sampled geometry is not a continuous collision proof',
            'Two cycles are a screening study, not generalization evidence',
            'Wrist-only test does not validate shoulder/elbow reverse travel'])
