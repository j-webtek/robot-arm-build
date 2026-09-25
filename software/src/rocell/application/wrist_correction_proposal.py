"""Offline experiment design from original trials; not a motor-command permit.

An encoder bias is a hypothesis, not calibration. Keep nominal endpoint and
experimental motor target distinct so a future executor cannot accept arrival
at the wrong target. This module has no transport, key access or retry path.
"""
import math
from functools import lru_cache
from statistics import median

from .absolute_wrist_result_review import summarize_absolute_wrist_trace
from .wrist_accuracy_analysis import reference_wrist_goal, STEP_RAD, REFERENCE_SHA256
from .first_motion_contract import canonical
from .wizard_diagnostic_coordinator import decode_diagnostic_json
from rocell.safety.absolute_wrist_review_authority import AbsoluteWristIntent


@lru_cache(maxsize=16)
def _historical_trace_bytes(request_bytes,trial_bytes,basis):
    """Cache only pure historical analysis, keyed by every original byte.

    At most sixteen bounded trials are retained. No live baseline, identity,
    deadline, signature, admission or filesystem check is cached. Exceptions
    are not cached. Serialized results prevent callers mutating cached values.
    """
    return canonical(summarize_absolute_wrist_trace(AbsoluteWristIntent(request_bytes),trial_bytes,expected_basis=basis))


def _historical_trace(request,raw,basis):
    if (type(request) is not AbsoluteWristIntent or type(request.canonical_bytes) is not bytes
            or len(request.canonical_bytes)>8192 or type(raw) is not bytes or len(raw)>256*1024
            or type(basis) is not str or len(basis)>128):
        raise ValueError('Bounded immutable historical trace inputs required')
    return decode_diagnostic_json(_historical_trace_bytes(request.canonical_bytes,raw,basis),maximum=65536)


def propose_wrist_correction(originals, *, expected_basis):
    """Revalidate 2–8 distinct trials before proposing one bounded experiment.

    Matching approach, start (within 0.5 degrees), USB unit and nominal target
    are required. Two repeats justify an experiment only, not a fitted model.
    Hashes identify supplied originals; they do not authenticate hardware.
    """
    if type(originals) is not list or not 2 <= len(originals) <= 8:
        raise ValueError('Two to eight original request/trial pairs required')
    rows, identities, contexts, attempts, references = [], [], [], set(), []
    for pair in originals:
        if type(pair) is not tuple or len(pair) != 2:
            raise ValueError('Exact request/trial tuple required')
        request, raw = pair
        trace = _historical_trace(request,raw,expected_basis)
        body = request.to_dict()
        key = (body['session_id'], body['attempt_id'])
        if key in attempts:
            raise ValueError('Duplicate attempt is not a repeat')
        attempts.add(key)
        if any(trace['trial_sha256'] == row['trial_sha256'] for row in rows):
            raise ValueError('Duplicate trial is not a repeat')
        rows.append(trace)
        identities.append(body['usb_identity'])
        contexts.append(body['draft']['expected_start_joints_rad'])
        references.append(body['references'])
    result = dict(schema='rocell.wrist_correction_proposal.v1', basis=expected_basis,
        status='HELD', reasons=[], evidence=rows, reference_source_sha256=REFERENCE_SHA256,
        supplied_usb_identities=identities, supplied_source_references=references,
        expected_start_contexts_rad=contexts, hardware_provenance_authenticated=False,
        nominal_target_deg=None, experimental_motor_target_deg=None,
        reference_goal_register=None, predicted_nominal_error_deg=None,
        approach_direction=None, observed_bias_deg=None, bias_spread_deg=None,
        arrival_tolerance_deg=0.5, maximum_commands=1, automatic_retry=False,
        motion_authorized=False, calibration_validated=False,
        installed_firmware_verified=False, sample_freshness_verified=False,
        assumption='LOCAL_CONSTANT_REPORTED_BIAS_SAME_APPROACH_AND_LOAD')
    reasons = result['reasons']
    if any(x != identities[0] for x in identities):
        reasons.append('USB_UNIT_MISMATCH')
    if any(row['status'] != 'REPORTED_TRACE_AVAILABLE' or
           row['endpoint_status'] not in ('TARGET_MISSED', 'REPORTED_SETTLED') or
           (row['final_constant_span_ns'] or 0) < 1_000_000_000 for row in rows):
        reasons.append('INVALID_OR_UNSETTLED_EVIDENCE')
    targets = [row['target_deg'] for row in rows]
    directions = [1 if row['target_deg'] > row['start_reported_deg'] else -1 for row in rows]
    if len(set(targets)) != 1 or len(set(directions)) != 1:
        reasons.append('TARGET_OR_APPROACH_MISMATCH')
    if max(row['start_reported_deg'] for row in rows)-min(row['start_reported_deg'] for row in rows) > .5:
        reasons.append('START_POSITION_MISMATCH')
    if any(math.degrees(abs(c[j]-contexts[0][j])) > .5
           for c in contexts for j in ('b','s','e','r','g')):
        reasons.append('OTHER_JOINT_CONTEXT_MISMATCH')
    if reasons:
        return result
    bias = median(row['final_error_deg'] for row in rows)
    spread = max(row['final_error_deg'] for row in rows)-min(row['final_error_deg'] for row in rows)
    result.update(nominal_target_deg=targets[0], approach_direction=directions[0],
                  observed_bias_deg=bias, bias_spread_deg=spread)
    if spread > math.degrees(STEP_RAD):
        reasons.append('BIAS_NOT_REPEATABLE_WITHIN_ONE_REFERENCE_STEP')
    if abs(bias) <= .5:
        reasons.append('ALREADY_WITHIN_NOMINAL_TOLERANCE')
    if abs(bias) > 1.5:
        reasons.append('OFFSET_EXCEEDS_EXPERIMENT_LIMIT')
    goal = reference_wrist_goal(math.radians(targets[0]-bias))
    # Feedback coordinates are not command coordinates (2048 vs 2047 midpoint).
    # The observed bias already includes that asymmetry; send the raw inverse
    # prediction and let the controller quantize it exactly once.
    candidate = targets[0]-bias
    if abs(candidate) > 10 or goal['clamped']:
        reasons.append('MOTOR_TARGET_OUTSIDE_EXPERIMENT_ENVELOPE')
    if reasons:
        return result
    result.update(status='OFFLINE_EXPERIMENT_CANDIDATE',
        experimental_motor_target_deg=candidate,
        reference_goal_register=goal['goal_register'],
        predicted_nominal_error_deg=candidate+bias-targets[0])
    return result
