"""Compact, display-only result for the existing bounded native move route.

This is not a verifier or permission to move. Preserve the complete native report
beside this projection; a receipt and a last reading are not proof of arrival.
"""
from copy import deepcopy
import math


def _number(value):
    return value if type(value) in (int, float) and math.isfinite(value) else None


def summarize_move(report, *, request_id, action_id):
    """Project a service-owned report without I/O or changes to native decisions."""
    outcome = report.get('outcome') or {}
    tx = outcome.get('transaction') or {}
    command = tx.get('command') or {}
    native_state = tx.get('state')
    attempts = tx.get('command_attempts')
    verification = tx.get('result') or {}
    arrived = (attempts == 1 and native_state == 'REPORTED_ENDPOINT_VERIFIED'
               and outcome.get('status') == 'REPORTED_ENDPOINT_VERIFIED'
               and verification.get('endpoint_verified') is True)
    # Cancellation after dispatch cannot establish that the robot stopped.
    # A completion timeout also does not prove a settled out-of-tolerance pose.
    status = 'ARRIVED_REPORTED' if arrived else 'EXECUTION_UNCERTAIN'
    if (attempts == 0 or (outcome.get('command_send_attempted') is False
                         and outcome.get('status') != 'ATTEMPT_ALREADY_USED')
            or (not tx and not report.get('outcome')
                         and report.get('status') == 'FAILED'
                         and report.get('baseline') is not None)):
        status = 'NOT_SENT'
    commanded = _number(command.get('rad'))
    desired = _number(tx.get('desired_endpoint_rad', commanded))
    rows = tx.get('rows') or []
    last = rows[-1] if rows else None
    pose = last[2] if isinstance(last, (list, tuple)) and len(last) == 3 else None
    observed = (_number(pose[4]) if isinstance(pose, (list, tuple))
                and len(pose) == 6 else None)
    degrees = lambda value: None if value is None else math.degrees(value)
    return dict(
        schema='rocell.move_result.v1', request_id=request_id, action_id=action_id,
        native_request_id=(outcome.get('move_request') or {}).get('request_id'),
        configuration_id=(outcome.get('move_request') or {}).get('configuration_id'),
        status=status, native_state=native_state, native_status=report.get('status'),
        reason=report.get('reason'), frame='CONTROLLER_JOINT', joint='r',
        desired_deg=degrees(desired), commanded_deg=degrees(commanded),
        last_reported_deg=degrees(observed), endpoint_verified=arrived,
        reported_minus_desired_deg=degrees(observed-desired)
        if observed is not None and desired is not None else None,
        command_attempts=attempts, command=deepcopy(command),
        correction_candidate=deepcopy(report.get('correction_candidate')),
        characterization=deepcopy(report.get('characterization')),
        evidence_pointer='/steps/0/report',
        measurement_source='CONTROLLER_JOINT_TELEMETRY',
        physical_accuracy_verified=False, automatic_retry_allowed=False,
        motion_authorized=False)
