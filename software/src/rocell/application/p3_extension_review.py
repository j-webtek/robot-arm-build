"""Offline P2 -> P3 timing review, bound to the measured P2 record."""
import hashlib
from pathlib import Path
from rocell.geometry import UrdfModel
from .large_pose_ladder import STEP_RAD, _sample
from .large_pose_relief_record import assess_large_pose_relief_record, decode_large_pose_relief_record

SOURCE_POSITIONS=(2047,2291,1825,2844,1784,2041,2047)
SOURCE_GOALS=(2047,2283,1831,2842,1785,2040,2047)
INTERMEDIATE_GOALS=(2047,2283,1831,2777,1785,2040,2047)
P3_GOALS=(2047,2283,1831,2777,1850,2040,2047)

def review_p3_extension(raw, *, expected_boot, model_path):
    assessment=assess_large_pose_relief_record(raw,expected_boot=expected_boot,profile='P2')
    endpoint=decode_large_pose_relief_record(raw,profile='P2')['endpoint'][-1]['joints']
    positions=tuple(j['position'] for j in endpoint)
    goals=tuple(j['goal'] for j in endpoint)
    if positions!=SOURCE_POSITIONS or goals!=SOURCE_GOALS:
        raise ValueError('Source differs from pinned measured P2 endpoint')
    path=Path(model_path).resolve();model=UrdfModel.from_file(path)
    angles=[-(positions[0]-2048)*STEP_RAD,(positions[1]-2048)*STEP_RAD,
            (positions[3]-1024)*STEP_RAD,(positions[4]-2048)*STEP_RAD,
            -(positions[5]-2048)*STEP_RAD]
    def sample(elbow,wrist):
        state=angles.copy();state[2]-=elbow*STEP_RAD;state[3]+=wrist*STEP_RAD
        points,distance=_sample(model,state)
        return points['hand_tcp'],distance-30
    def envelope(pairs):
        rows=[(e,w,*sample(e,w)) for e,w in pairs]
        low=min(rows,key=lambda row:row[2][2])
        return dict(samples=len(rows),minimum_tcp_z_mm=low[2][2],
                    minimum_capsule_clearance_mm=min(row[3] for row in rows),
                    lowest_progress_counts=[low[0],low[1]])
    grid=[65*i/40 for i in range(41)]
    return dict(schema='rocell.p3_extension_review.v1',source_assessment=assessment,
        source_record_sha256=hashlib.sha256(raw).hexdigest(),
        model_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
        source_positions=list(positions),source_goals=list(goals),
        intermediate_name='P3E',intermediate_goals=list(INTERMEDIATE_GOALS),
        later_p3_goals=list(P3_GOALS),
        start_tcp_mm=list(sample(0,0)[0]),elbow_first_tcp_mm=list(sample(65,0)[0]),
        wrist_first_tcp_mm=list(sample(0,65)[0]),nominal_p3_tcp_mm=list(sample(65,65)[0]),
        independent_progress=envelope((e,w) for e in grid for w in grid),
        elbow_first=envelope([(e,0) for e in grid]+[(65,w) for w in grid]),
        first_step_full_travel=envelope((i/2,0) for i in range(161)),
        next_command=dict(servo_id=14,target=2777,command_delta_counts=-65,
                          target_minus_measured_position_counts=-67,speed=20,acceleration=1,
                          source_tolerance_counts=3,endpoint_tolerance_counts=12,
                          passive_drift_counts=2,maximum_travel_counts=80,maximum_writes=1),
        assumptions=['Nominal endpoint retains prior joint bias; not calibrated compensation',
                     'No cables, full link meshes, tool or registered board',
                     'Discrete samples are not a continuous collision proof',
                     'Other joints fixed; full multi-joint uncertainty is not modeled'],
        hardware_access=False,movement_authorized=False,physical_clearance_verified=False,
        retry_allowed=False,automatic_wrist_follow_on=False)
