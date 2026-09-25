"""Recompute absolute-target endpoint evidence from complete original captures.

Reports establish data consistency, not worker identity, servo freshness or
physical accuracy. Incomplete capture envelopes remain failure diagnostics.
"""
import base64
import hashlib
import math

from rocell.arm.first_motion_analysis import _window
from rocell.arm.protocol import encode_line
from rocell.arm.wrist_endpoint_verification import verify_reported_wrist
from rocell.motion.absolute_wrist_diagnostic import (
    AbsoluteWristDiagnosticDraft, preview_absolute_wrist_from_capture,
)
from rocell.safety.absolute_wrist_review_authority import AbsoluteWristIntent
from .absolute_wrist_capture import validate_absolute_wrist_capture
from .first_motion_contract import canonical
from .observational_command_binding import MAX_SELECTED_BASELINE_AGE_NS
from .wizard_diagnostic_coordinator import decode_diagnostic_json


def summarize_absolute_wrist_trace(request, raw, *, expected_basis):
    """Offline diagnostics, never a substitute for the endpoint acceptance gate.

    Revalidate originals before calculating a conservative constant-report span.
    Equal buffered reports do not prove physical stillness or fresh samples.
    The span excludes both edge read durations and is absent for invalid data.
    """
    review = review_absolute_wrist_result(request, raw, expected_basis=expected_basis)
    trial = decode_diagnostic_json(raw, maximum=256 * 1024)
    post, write = trial['post'], trial['write']
    data = validate_absolute_wrist_capture(request, post, phase='post',
                                          command_completed_ns=write['finished_ns'])
    rows, issues, _ = _window(data, post['read_windows'], post['started_ns'], post['window_deadline_ns'])
    result = dict(schema='rocell.absolute_wrist_trace_diagnostic.v1',
        request_sha256=request.request_sha256, trial_sha256=review['trial_sha256'],
        basis=expected_basis, endpoint_status=review['endpoint']['status'],
        status='UNAVAILABLE', sample_count=len(rows), final_reported_deg=None,
        target_deg=math.degrees(review['preview']['candidate_command']['rad']),
        start_reported_deg=math.degrees(review['preview']['reported_start_rad']),
        final_error_deg=None, final_constant_report_count=0,
        final_constant_span_ns=None, final_value_first_read_after_write_ns=None,
        sample_freshness_verified=False, physical_accuracy_verified=False,
        campaign_advance_allowed=False, motion_authorized=False)
    if issues or review['capture_issues'] or not review['transport_clean'] or not rows:
        return result
    final = rows[-1][2][3]
    first = len(rows)-1
    while first > 0 and rows[first-1][2][3] == final:
        first -= 1
    result.update(status='REPORTED_TRACE_AVAILABLE', final_reported_deg=math.degrees(final),
        final_error_deg=math.degrees(review['endpoint']['final_error_rad']),
        final_constant_report_count=len(rows)-first,
        final_constant_span_ns=max(0, rows[-1][0]-rows[first][1]),
        final_value_first_read_after_write_ns=[rows[first][0]-write['finished_ns'],
                                              rows[first][1]-write['finished_ns']])
    return result


def review_absolute_wrist_result(request, raw, *, expected_basis):
    if (type(request) is not AbsoluteWristIntent or type(raw) is not bytes
            or expected_basis not in ('SYNTHETIC_WIRE_REHEARSAL', 'RETAINED_PHYSICAL_CAPTURE')):
        raise ValueError('Exact request, original bytes and evidence basis required')
    trial = decode_diagnostic_json(raw, maximum=256 * 1024)
    fields = {'schema', 'request_sha256', 'basis', 'baseline', 'post', 'write', 'cleanup'}
    if (type(trial) is not dict or set(trial) != fields or canonical(trial) != raw
            or trial['schema'] != 'rocell.absolute_wrist_trial.v1'
            or trial['request_sha256'] != request.request_sha256 or trial['basis'] != expected_basis):
        raise ValueError('Exact original absolute diagnostic result required')
    body = request.to_dict()
    baseline, post, write, cleanup = (trial[k] for k in ('baseline', 'post', 'write', 'cleanup'))
    write_fields = {'payload_base64', 'started_ns', 'finished_ns', 'attempted',
                    'confirmed_bytes', 'completion_uncertain'}
    if (type(write) is not dict or set(write) != write_fields
            or write['attempted'] is not True or type(write['completion_uncertain']) is not bool
            or type(write['payload_base64']) is not str or len(write['payload_base64']) > 1024
            or any(type(write[k]) is not int for k in ('started_ns', 'finished_ns', 'confirmed_bytes'))
            or not body['issued_ns'] <= write['started_ns'] <= write['finished_ns'] < body['deadline_ns']
            or write['finished_ns'] - write['started_ns'] > 1_000_000_000):
        raise ValueError('Exact bounded write accounting required')
    before = validate_absolute_wrist_capture(request, baseline, phase='baseline')
    after = validate_absolute_wrist_capture(request, post, phase='post',
                                           command_completed_ns=write['finished_ns'])
    if (baseline['finished_ns'] > write['started_ns']
            or post['started_ns'] - write['finished_ns'] > 100_000_000):
        raise ValueError('Baseline/write/post acquisition order changed')
    draft = AbsoluteWristDiagnosticDraft(canonical(body['draft']))
    preview = preview_absolute_wrist_from_capture(draft, before, baseline['read_windows'],
        started_ns=baseline['started_ns'], finished_ns=baseline['finished_ns'], now_ns=write['started_ns'])
    expected_payload = encode_line(preview['candidate_command'])
    if (write['payload_base64'] != base64.b64encode(expected_payload).decode('ascii')
            or not 0 <= write['confirmed_bytes'] <= len(expected_payload)
            or write['started_ns'] - preview['baseline_last_host_received_ns'] > MAX_SELECTED_BASELINE_AGE_NS):
        raise ValueError('Actual command, byte accounting or selected baseline differs')
    cleanup_fields = {'started_ns', 'finished_ns', 'all_handles_closed', 'pending_io_count'}
    if (type(cleanup) is not dict or set(cleanup) != cleanup_fields
            or type(cleanup['all_handles_closed']) is not bool
            or type(cleanup['pending_io_count']) is not int or cleanup['pending_io_count'] < 0
            or any(type(cleanup[k]) is not int for k in ('started_ns', 'finished_ns'))
            or not post['finished_ns'] <= cleanup['started_ns'] <= cleanup['finished_ns'] <= body['deadline_ns']
            or cleanup['finished_ns'] - cleanup['started_ns'] > 2_000_000_000):
        raise ValueError('Exact bounded cleanup accounting required')
    before_rows, before_issues, _ = _window(before, baseline['read_windows'],
                                          baseline['started_ns'], baseline['window_deadline_ns'])
    after_rows, issues, framing = _window(after, post['read_windows'],
                                        post['started_ns'], post['window_deadline_ns'])
    clean = (write['confirmed_bytes'] == len(expected_payload) and not write['completion_uncertain']
             and cleanup['all_handles_closed'] and cleanup['pending_io_count'] == 0)
    endpoint = verify_reported_wrist(after_rows, start=before_rows[-1][2],
        target=preview['candidate_command']['rad'], capture_issues=issues | before_issues,
        transport_clean=clean)
    return dict(schema='rocell.absolute_wrist_result_review.v1',
        request_sha256=request.request_sha256, trial_sha256=hashlib.sha256(raw).hexdigest(),
        basis=expected_basis, preview=preview, endpoint=endpoint, post_framing=framing,
        post_samples=len(after_rows), capture_issues=sorted(issues | before_issues),
        transport_clean=clean, owned_process_verified=False, physical_movement_verified=False,
        physical_stop_verified=False, motion_authorized=False, campaign_advance_allowed=False)
