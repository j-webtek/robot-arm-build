"""Bounded wrist-response diagnostics from original bytes, never motion approval.

Thresholds below are provisional diagnostic thresholds, not calibrated accuracy
or protective limits. Reported joint changes may be cached command values;
independent physical observation remains required even when telemetry agrees.
"""
import math

from rocell.application.first_motion_contract import FirstMotionRequest
from .telemetry_coverage import complete_frame_interval, iter_window_records

JOINTS = ('b', 's', 'e', 't', 'r', 'g')
TOLERANCE_RAD = math.radians(0.5)
MAX_GAP_NS = 100_000_000
DWELL_NS = 200_000_000


def _window(raw, windows, begin_ns, end_ns, *, maximum_bytes=65536):
    selected, selected_windows, framing = complete_frame_interval(raw, windows, maximum_bytes=maximum_bytes)
    issues = set()
    if selected and not selected.endswith(b'\n'):
        issues.add('UNFRAMED_BYTES')
    rows = []
    previous = begin_ns
    for record in iter_window_records(selected, selected_windows, maximum_bytes=maximum_bytes):
        begin, finish = record['host_acquisition_bounds_ns']
        if not begin_ns <= begin <= finish <= end_ns:
            issues.add('FRAME_OUTSIDE_WINDOW')
            continue
        if finish - previous > MAX_GAP_NS or finish - begin > MAX_GAP_NS:
            issues.add('READ_COVERAGE_GAP')
        previous = finish
        fields = record.get('fields', {})
        if record['kind'] != 'POSE_TELEMETRY' or any(
            type(fields.get(j)) not in (int, float) or not math.isfinite(fields[j])
            or abs(fields[j]) > 100 for j in JOINTS
        ):
            issues.add('INVALID_JOINT_RECORD')
            continue
        rows.append((begin, finish, tuple(fields[j] for j in JOINTS)))
    if end_ns - previous > MAX_GAP_NS:
        issues.add('READ_COVERAGE_GAP')
    if len(rows) < 2:
        issues.add('INSUFFICIENT_SAMPLES')
    return rows, issues, framing


def analyze_first_motion(request, baseline_raw, baseline_windows, post_raw, post_windows,
                         *, baseline_started_ns, baseline_finished_ns,
                         write_started_ns, write_finished_ns, observation_end_ns, basis):
    """Analyze every retained line; no sample filtering may manufacture success.

    Caller retains write outcome, cleanup and independent observation separately.
    This result deliberately does not classify physical success or qualification.
    """
    times = (baseline_started_ns, baseline_finished_ns, write_started_ns,
             write_finished_ns, observation_end_ns)
    if (type(request) is not FirstMotionRequest
            or basis not in {'SYNTHETIC_WIRE_REHEARSAL', 'RETAINED_PHYSICAL_CAPTURE'}
            or any(type(t) is not int or not 0 < t < 2**63 for t in times)
            or not times[0] < times[1] <= times[2] <= times[3] < times[4]):
        raise ValueError('Exact request and ordered host acquisition times required')
    body = request.to_dict()
    if (times[0] < body['issued_monotonic_ns'] or times[-1] > body['deadline_monotonic_ns']
            or times[1]-times[0] > 1_000_000_000 or times[-1]-times[3] > 5_000_000_000):
        raise ValueError('Observation exceeds commissioning request window')
    before, bi, bf = _window(baseline_raw, baseline_windows, times[0], times[1])
    after, pi, pf = _window(post_raw, post_windows, times[3], times[4])
    issues = {'BASELINE_'+i for i in bi} | {'POST_'+i for i in pi}
    start = before[-1][2] if before else None
    latest = after[-1][2] if after else None
    target = body['command']['rad']
    changed = False
    other_changed = False
    dwell_begin = None
    dwell_bounds = None
    if before:
        if before[-1][0]-before[0][1] < 100_000_000:
            issues.add('BASELINE_INSUFFICIENT_TIME_SPAN')
        if any(abs(row[2][i]-start[i]) > TOLERANCE_RAD for row in before for i in range(6)):
            issues.add('BASELINE_UNSTABLE')
        low, high = map(math.radians, body['independent_start_interval_deg'])
        if any(not low <= row[2][3] <= high for row in before):
            issues.add('REPORTED_START_OUTSIDE_DECLARED_INTERVAL')
        for begin, finish, joints in after:
            changed |= abs(joints[3]-start[3]) > TOLERANCE_RAD
            if not min(start[3],target)-TOLERANCE_RAD <= joints[3] <= max(start[3],target)+TOLERANCE_RAD:
                issues.add('REPORTED_WRIST_EXCURSION')
            other_changed |= any(abs(joints[i]-start[i]) > TOLERANCE_RAD for i in (0,1,2,4,5))
            if abs(joints[3]-target) <= TOLERANCE_RAD:
                if dwell_begin is None:
                    dwell_begin = (begin, finish)
                if begin-dwell_begin[1] >= DWELL_NS:
                    dwell_bounds = list(dwell_begin)
            else:
                dwell_begin = dwell_bounds = None
    if not changed:
        issues.add('NO_RESOLVABLE_REPORTED_WRIST_CHANGE')
    if other_changed:
        issues.add('OTHER_REPORTED_JOINT_CHANGED')
    if dwell_bounds is None:
        issues.add('NO_FINAL_REPORTED_TARGET_DWELL')
    return {
        'schema':'rocell.first_motion_analysis.v1', 'basis':basis,
        'request_sha256':request.request_sha256,
        'status':'INSUFFICIENT_OR_UNEXPECTED_TELEMETRY' if issues else 'REPORTED_WRIST_RESPONSE_REVIEW_REQUIRED',
        'issues':sorted(issues), 'baseline_count':len(before), 'post_count':len(after),
        'baseline_framing':bf, 'post_framing':pf,
        'reported_start_joints_rad':dict(zip(JOINTS,start)) if start else None,
        'latest_reported_joints_rad':dict(zip(JOINTS,latest)) if latest else None,
        'host_target_dwell_entry_bounds_ns':dwell_bounds if not issues else None,
        'diagnostic_tolerance_rad':TOLERANCE_RAD, 'max_host_read_gap_ns':MAX_GAP_NS,
        'physical_movement_verified':False, 'device_sample_freshness_verified':False,
        'endpoint_baseline_qualified':False, 'motion_authorized':False,
        'campaign_advance_allowed':False,
    }
