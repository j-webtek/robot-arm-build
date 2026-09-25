"""Attach historical wrist-planning diagnostics to an owned capture's UI view.

This adapter never opens a device or renews old evidence. It examines the entire
capture before selecting its final one-second baseline for an offline preview.
"""
import base64
import binascii
import hashlib

from rocell.arm.first_motion_analysis import _window, JOINTS
from rocell.motion.observational_wrist_plan import preview_observational_wrist


def summarize_capture(observation):
    result = dict(schema='rocell.observational_capture_preview.v1',
        status='HELD', historical_only=True, connected=False,
        motion_authorized=False, precision_measurements_required=False,
        capture_sha256=None, preview=None,
        message='Historical diagnostic only; live execution requires a new owned baseline.')
    try:
        samples, end, details = decode_historical_baseline(observation)
        result.update(details)
        preview = preview_observational_wrist(samples=samples, now_ns=end)
        result.update(status='HISTORICAL_PREVIEW_AVAILABLE', preview=preview)
    except (ValueError, KeyError, TypeError, binascii.Error) as error:
        # A diagnostic failure must not suppress the original USB result/export.
        result['hold_reason'] = str(error)[:512]
    return result

def decode_historical_baseline(observation):
    """Validate every frame before choosing a time-defined tail; no freshness claim."""
    if type(observation) is not dict or observation.get('schema') not in {
            'rocell.powered_telemetry_observation.v2', 'rocell.powered_telemetry_observation.v3'}:
        raise ValueError('Expected retained telemetry observation')
    if observation.get('status') != 'CAPTURED_CLOSED' or observation.get('errors') != []:
        raise ValueError('Capture did not finish cleanly')
    blob = observation['capture']['raw']
    if (type(blob) is not dict or set(blob) != {'bytes', 'sha256', 'base64'}
            or type(blob['base64']) is not str or len(blob['base64']) > 87384):
        raise ValueError('Bounded capture original required')
    raw = base64.b64decode(blob['base64'], validate=True)
    digest = hashlib.sha256(raw).hexdigest()
    if type(blob['bytes']) is not int or blob['bytes'] != len(raw) or len(raw) > 65536 or digest != blob['sha256']:
        raise ValueError('Capture original hash or length mismatch')
    begin, end = observation['started_monotonic_ns'], observation['observation_finished_monotonic_ns']
    if (type(begin) is not int or type(end) is not int
            or not 0 < begin < end < 2**63 or end - begin > 10_000_000_000):
        raise ValueError('Bounded historical capture times required')
    acquisition = begin
    if observation['schema'] == 'rocell.powered_telemetry_observation.v3':
        acquisition = observation.get('acquisition_started_monotonic_ns')
        if (type(acquisition) is not int or not begin <= acquisition < end
                or any(row[2] < acquisition for row in observation['read_windows'])):
            raise ValueError('Invalid acquisition start or pre-acquisition read')
    rows, issues, framing = _window(raw, observation['read_windows'], acquisition, end)
    if issues:
        raise ValueError('Capture issues: ' + ', '.join(sorted(issues)))
    # Select a time-defined tail, not whichever samples happen to pass.
    # Full-capture malformed records and gaps were already checked above.
    selected = [row for row in rows if row[0] >= end - 1_000_000_000]
    if len(selected) < 2 or selected[-1][0] - selected[0][1] < 100_000_000:
        raise ValueError('Insufficient distinct final baseline span')
    samples = [dict(host_received_ns=finish, joints_rad=dict(zip(JOINTS, joints)))
               for start, finish, joints in selected]
    return samples, end, dict(capture_sha256=digest, full_capture_frame_count=len(rows),
        startup_duration_ns=acquisition-begin,
        acquisition_started_monotonic_ns=acquisition,
        startup_timing_separated=observation['schema'] == 'rocell.powered_telemetry_observation.v3',
        selected_frame_count=len(selected), selected_acquisition_bounds_ns=[selected[0][0], selected[-1][1]],
        raw_capture_framing=framing)
