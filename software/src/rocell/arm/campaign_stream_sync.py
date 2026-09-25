"""Versioned baseline partitioning over retained bytes; no reads or dispatch.

The first line is synchronization data regardless of whether it parses. Never
scan past a bad second line. This is an explicitly reserved startup boundary,
not a rule for repairing arbitrary malformed baseline or post-command data.
"""
import hashlib
from .cross_window_framing import analyze_cross_command_post
from .first_motion_analysis import _window
from .telemetry_coverage import _validate

SYNC_SCHEMAS=('rocell.attended_positional_intent.v7','rocell.attended_positional_intent.v8',
    'rocell.attended_positional_intent.v9','rocell.attended_positional_intent.v10',
    'rocell.attended_positional_intent.v11','rocell.attended_positional_intent.v12',
    'rocell.attended_positional_intent.v13','rocell.attended_positional_intent.v14',
    'rocell.attended_positional_intent.v15','rocell.attended_positional_intent.v16',
    'rocell.attended_positional_intent.v17', 'rocell.attended_positional_intent.v18', 'rocell.attended_positional_intent.v19', 'rocell.attended_positional_intent.v20', 'rocell.attended_positional_intent.v21', 'rocell.attended_positional_intent.v22')

FRAMED_SCHEMA = 'rocell.attended_positional_intent.v21'
FRAMED_SCHEMAS = (FRAMED_SCHEMA, 'rocell.attended_positional_intent.v22')


class CampaignFramingError(ValueError):
    """Bounded diagnostic reason, safe for retained native errors."""
    def __init__(self, reason):
        allowed={'BOUNDARY_ORIGINAL_OR_COVERAGE_MISMATCH','BOUNDARY_TIME_GAP_OR_ORDER',
            'BASELINE_FRAME_BOUNDARY_UNAVAILABLE','BOUNDARY_FRAGMENT_MISSING_OR_OVERLONG',
            'CROSSING_FRAME_NOT_VALID_POSE','CROSSING_FRAME_ACQUISITION_GAP',
            'POST_CAPTURE_TIME_BOUNDS','POST_FEEDBACK_INVALID'}
        self.reason=reason if reason in allowed else 'CROSS_WINDOW_VALIDATION_FAILED'
        super().__init__(self.reason)


def campaign_post_window(body, raw, windows, begin_ns, end_ns, *,
                         baseline_raw, baseline_windows, write_started_ns, write_finished_ns):
    """One version gate shared by native admission, reconstruction and exports.

    Callers authenticate the original captures first. Older schemas deliberately
    keep their historical decoder; v21 excludes only the proven crossing frame.
    """
    if body['schema'] not in FRAMED_SCHEMAS:
        return _window(raw, windows, begin_ns, end_ns,
                       maximum_bytes=body['limits']['maximum_raw_bytes_per_leg'])
    try:
        return analyze_cross_command_post(baseline_raw, baseline_windows, raw, windows,
            baseline_sha256=hashlib.sha256(baseline_raw).hexdigest(),
            post_sha256=hashlib.sha256(raw).hexdigest(),
            write_started_ns=write_started_ns, write_finished_ns=write_finished_ns,
            post_started_ns=begin_ns, post_finished_ns=end_ns)
    except (ValueError, TypeError, IndexError, KeyError) as error:
        raise CampaignFramingError(str(error)) from error


def campaign_window(body, phase, raw, windows, begin_ns, end_ns, *, maximum_bytes):
    if body['schema'] not in SYNC_SCHEMAS or phase!='baseline':
        return _window(raw,windows,begin_ns,end_ns,maximum_bytes=maximum_bytes)
    _validate(raw,windows,maximum_bytes=maximum_bytes)
    boundary=raw.find(b'\n')+1
    if not 0<boundary<=4096:
        raise ValueError('Synchronization delimiter absent or over byte budget')
    delimiter=next(row for row in windows if row[0]<boundary<=row[1])
    if not begin_ns<=delimiter[2]<=delimiter[3]<=begin_ns+250_000_000:
        raise ValueError('Synchronization delimiter outside startup budget')
    selected=raw[boundary:]
    shifted=[[max(a,boundary)-boundary,b-boundary,start,finish]
        for a,b,start,finish in windows if b>boundary]
    if not shifted or end_ns-shifted[0][3]<1_000_000_000:
        raise ValueError('Full clean baseline duration unavailable after synchronization')
    rows,issues,framing=_window(selected,shifted,shifted[0][2],end_ns,maximum_bytes=maximum_bytes)
    # _window supports historical partial-prefix recognition. A synchronized
    # interval starts on a known boundary, so ANY further skipped prefix fails.
    if framing['analysis_range'][0]!=0:
        issues.add('UNEXPECTED_PREFIX_AFTER_SYNCHRONIZATION')
    if not rows or rows[-1][0]-rows[0][1]<1_000_000_000:
        issues.add('INSUFFICIENT_CLEAN_BASELINE_SPAN')
    return rows,issues,dict(schema='rocell.campaign_stream_sync.v1',
        original_sha256=hashlib.sha256(raw).hexdigest(),original_bytes=len(raw),
        startup_range=[0,boundary],startup_sha256=hashlib.sha256(raw[:boundary]).hexdigest(),
        startup_content_validated=False,delimiter_acquisition_bounds_ns=delimiter[2:4],
        baseline_range=[boundary,len(raw)],baseline_framing=framing,
        device_sample_freshness_verified=False,motion_authorized=False)
