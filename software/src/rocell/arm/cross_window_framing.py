"""Hash-bound explanation of a frame spanning a command boundary.

This proves byte/syntax consistency, not lossless USB transport or device sample
freshness. The crossing frame is never counted as post-command evidence. Native
admission opts in only through v21; historical schema verdicts stay unchanged.
"""
import hashlib
import math

from .telemetry_coverage import _validate
from .telemetry_stream import decode_telemetry_line
from .first_motion_analysis import _window


def partition_cross_command_frame(baseline_raw, baseline_windows, post_raw, post_windows, *,
                                  baseline_sha256, post_sha256,
                                  write_started_ns, write_finished_ns):
    """Exclude only a verified crossing frame, preserving original offsets.

    Expected digests must come from the caller's independently verified originals.
    Capture windows must cover every byte. No search past the FIRST post LF is
    allowed. Bad/missing fragments reject the explanation, not just the line.
    """
    for raw, windows, digest, maximum in (
        (baseline_raw, baseline_windows, baseline_sha256, 65536),
        (post_raw, post_windows, post_sha256, 524288)):
        _validate(raw, windows, maximum_bytes=maximum)
        if not windows or not raw or hashlib.sha256(raw).hexdigest() != digest:
            raise ValueError('BOUNDARY_ORIGINAL_OR_COVERAGE_MISMATCH')
    if (type(write_started_ns) is not int or type(write_finished_ns) is not int
            or not 0 < baseline_windows[-1][3] <= write_started_ns <= write_finished_ns <= post_windows[0][2]
            or post_windows[0][3]-baseline_windows[-1][3] > 250_000_000):
        raise ValueError('BOUNDARY_TIME_GAP_OR_ORDER')
    last_lf = baseline_raw.rfind(b'\n')
    if last_lf < 0:
        raise ValueError('BASELINE_FRAME_BOUNDARY_UNAVAILABLE')
    tail_start = last_lf+1
    tail = baseline_raw[tail_start:]
    proof = dict(schema='rocell.cross_command_frame_partition.v1',
        baseline_sha256=baseline_sha256, post_sha256=post_sha256,
        baseline_bytes=len(baseline_raw), post_bytes=len(post_raw),
        baseline_tail_range=[tail_start,len(baseline_raw)],
        post_excluded_range=[0,0], post_analysis_range=[0,len(post_raw)],
        joined_frame_sha256=None, joined_frame_bytes=0,
        crossing_frame_counted_as_post=False, byte_continuity_consistent=False,
        transport_continuity_verified=False, motion_authorized=False)
    if not tail:
        proof['status']='ALIGNED_NO_PARTITION'
        return post_raw, [list(w) for w in post_windows], proof
    boundary = post_raw.find(b'\n')+1
    if (not tail.startswith(b'{') or not 0 < boundary
            or len(tail)+boundary > 4096):
        raise ValueError('BOUNDARY_FRAGMENT_MISSING_OR_OVERLONG')
    joined = tail+post_raw[:boundary]
    record = decode_telemetry_line(joined,0,len(joined))
    if (record['kind']!='POSE_TELEMETRY'
            or any(type(record['fields'][k]) not in (int,float)
                   or not math.isfinite(record['fields'][k]) or abs(record['fields'][k])>100
                   for k in ('b','s','e','t','r','g'))):
        raise ValueError('CROSSING_FRAME_NOT_VALID_POSE')
    tail_reads=[w for w in baseline_windows if w[1]>tail_start]
    prefix_reads=[w for w in post_windows if w[0]<boundary and w[1]>0]
    # Bound acquisition of the whole crossing record, not just the two reads
    # adjacent to the write. A slowly accumulated fragment is not fresh proof.
    if prefix_reads[-1][3] - tail_reads[0][2] > 250_000_000:
        raise ValueError('CROSSING_FRAME_ACQUISITION_GAP')
    shifted=[[max(a,boundary)-boundary,b-boundary,begin,end]
             for a,b,begin,end in post_windows if b>boundary]
    selected=post_raw[boundary:]
    _validate(selected,shifted,maximum_bytes=524288)
    proof.update(status='CROSSING_FRAME_EXCLUDED', byte_continuity_consistent=True,
        post_excluded_range=[0,boundary],post_analysis_range=[boundary,len(post_raw)],
        joined_frame_sha256=hashlib.sha256(joined).hexdigest(),joined_frame_bytes=len(joined),
        baseline_tail_host_bounds_ns=[tail_reads[0][2],tail_reads[-1][3]],
        post_prefix_host_bounds_ns=[prefix_reads[0][2],prefix_reads[-1][3]])
    return selected,shifted,proof


def analyze_cross_command_post(baseline_raw, baseline_windows, post_raw, post_windows, *,
                               post_started_ns, post_finished_ns, **binding):
    """Return diagnostic rows/issues; do not forgive any interior rejected line."""
    if (type(post_started_ns) is not int or type(post_finished_ns) is not int
            or not 0 < post_started_ns <= post_finished_ns
            or any(not post_started_ns <= w[2] <= w[3] <= post_finished_ns for w in post_windows)):
        raise ValueError('POST_CAPTURE_TIME_BOUNDS')
    selected,windows,proof=partition_cross_command_frame(
        baseline_raw,baseline_windows,post_raw,post_windows,**binding)
    rows,issues,framing=_window(selected,windows,post_started_ns,post_finished_ns,
                                 maximum_bytes=524288)
    # The partition establishes a frame boundary. Generic legacy prefix
    # recognition must not skip a second malformed record after that point.
    if framing['analysis_range'][0]!=0:
        issues.add('UNPROVED_PREFIX_AFTER_BOUNDARY')
    proof['remaining_capture_framing']=framing
    return rows,issues,proof
