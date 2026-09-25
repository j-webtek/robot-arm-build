"""Offline, predeclared local correction experiment; no controller transport."""
import hashlib
from pathlib import Path

from rocell.geometry import UrdfModel
from .large_pose_ladder import STEP_RAD, _sample
from .p4_repeat_campaign_review import GOALS, MODEL_SHA
POSITIONS = (2047,2225,1890,2716,1978,2041,2047)

ORDER = ('baseline', 'candidate', 'candidate', 'baseline',
         'candidate', 'baseline', 'baseline', 'candidate')
DESIRED = 1947
COMMANDS = {'baseline': 1944, 'candidate': 1945}


def review_comparison(model_path):
    path = Path(model_path).resolve()
    if hashlib.sha256(path.read_bytes()).hexdigest() != MODEL_SHA:
        raise ValueError('Reviewed kinematic model required')
    legs = []
    lower, upper = [], []
    previous = GOALS[4]
    for condition in ORDER:
        for role, target in (('comparison', COMMANDS[condition]), ('anchor', 1980)):
            ordinal = len(legs) + 1
            lo, hi = ((POSITIONS[4]-3, POSITIONS[4]+3) if ordinal == 1
                      else (previous-12, previous+12))
            direction = 1 if target > previous else -1
            lower.append(lo-80 if direction < 0 else lo-1)
            upper.append(hi+80 if direction > 0 else hi+1)
            legs.append(dict(leg=ordinal, role=role, condition=condition,
                desired_endpoint=DESIRED if role == 'comparison' else 1980,
                transmitted_goal=target, required_goal_readback=target,
                preceding_command_goal=previous, direction=direction,
                command_delta_counts=target-previous, servo_id=15,
                speed=20, acceleration=1, maximum_write_attempts=1))
            previous = target
    model = UrdfModel.from_file(path)
    low, high = min(lower), max(upper)
    samples = []
    for half in range(low*2, high*2+1):
        angles = [-(POSITIONS[0]-2048)*STEP_RAD, (POSITIONS[1]-2048)*STEP_RAD,
                  (POSITIONS[3]-1024)*STEP_RAD, (half/2-2048)*STEP_RAD,
                  -(POSITIONS[5]-2048)*STEP_RAD]
        points, separation = _sample(model, angles)
        samples.append((points['hand_tcp'][2], separation-30))
    return dict(schema='rocell.p4_midpoint_comparison.v1', order=ORDER,
        source_positions=POSITIONS, source_goals=GOALS, legs=legs,
        model_sha256=MODEL_SHA, maximum_writes=len(legs),
        wrist_sweep_counts=[low, high], sweep_samples=len(samples),
        minimum_model_tcp_z_mm=min(z for z, _ in samples),
        minimum_model_capsule_clearance_mm=min(c for _, c in samples),
        hypothesis='Command 1945 may arrive at desired readback 1947 from above; unseen command, unvalidated',
        acceptance=dict(required_comparison_arrivals=8, arrivals_per_condition=4,
            candidate_max_absolute_desired_error_counts=1,
            candidate_max_mean_absolute_desired_error_counts=0.5,
            candidate_max_spread_counts=1,
            require_all_16_legs_verified_and_exported=True),
        execution_requirements=[
            'Fresh stable source and prewrite checks; retained source is not live state',
            'All comparison approaches from high anchor goal 1980; measured anchor must be 1977..1979',
            'Record actual anchor position and stratify errors by it; imbalance limits interpretation',
            'Separate desired endpoint, transmitted goal, readback goal and measured position',
            'Retain existing 12-count command-arrival, 80-count travel, fresh feedback and global passive-drift bounds',
            'Scientific failure does not relax motion bounds or trigger extra trials or retuning',
            'Export each leg before explicit next-leg admission; no automatic retry or recovery',
            'Stop affected sequence on uncertain delivery, invalid feedback, drift, timeout or export failure'],
        limitations=[
            'Readback improvement is not externally measured stylus accuracy',
            'Fixed passive angles only; no full joint-uncertainty, mesh, cable, tool or registered board proof',
            'Discrete geometric samples are not continuous collision proof',
            'Four arrivals per condition provide a local screening result, not generalization',
            'r73 cannot execute this route; new candidate contracts and tests required before deployment'],
        hardware_access=False, movement_authorized=False, physical_clearance_verified=False,
        compensation_applied=False, native_comparison_implemented=False)
