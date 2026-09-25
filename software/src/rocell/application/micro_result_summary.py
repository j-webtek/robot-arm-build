"""Display-only projection of retained reports; never admission or verification.

Keep command error distinct from desired-endpoint error. Missing evidence stays
null, including on interrupted transactions; a display value cannot imply success.
"""
import math


def _degrees(value):
    return math.degrees(value) if type(value) in (int, float) and math.isfinite(value) else None


def _roll(pose):
    return _degrees(pose[4]) if isinstance(pose, (list, tuple)) and len(pose) == 6 else None


def _leg(name, status, command, desired, observed, hold):
    reconstruction = (hold or {}).get('reconstruction') or {}
    return dict(leg=name, status=status or 'UNAVAILABLE', command_deg=command,
                desired_deg=desired, observed_deg=observed,
                command_error_deg=None if observed is None or command is None else observed-command,
                desired_error_deg=None if observed is None or desired is None else observed-desired,
                hold_status=(hold or {}).get('status', 'NOT_RUN'),
                hold_samples=reconstruction.get('successful_originals'),
                hold_response_span_s=reconstruction.get('response_span_s'),
                hold_max_gap_ms=reconstruction.get('maximum_response_gap_ms'))


def summarize_micro_result(report):
    """Consume service-owned reports without I/O, changing no native decisions."""
    legs = []
    predecessor = report.get('predecessor')
    if predecessor is not None:
        tx = (predecessor.get('outcome') or {}).get('transaction') or {}
        rows = tx.get('rows') or []
        # Show observations only from an endpoint-verifier result, not an ACK.
        observed = _roll(rows[-1][2]) if rows and tx.get('state') == 'REPORTED_ENDPOINT_VERIFIED' else None
        command = _degrees((tx.get('command') or {}).get('rad'))
        desired = _degrees(tx.get('desired_endpoint_rad', (tx.get('command') or {}).get('rad')))
        legs.append(_leg('Predecessor', predecessor.get('status'), command, desired,
                         observed, report.get('predecessor_hold')))
    micro = report.get('micro')
    if micro is not None:
        context = micro.get('context') or {}
        endpoint = micro.get('endpoint') or {}
        legs.append(_leg('Optional micro-command', micro.get('status'),
                         _degrees((context.get('command') or {}).get('rad')),
                         _degrees(endpoint.get('desired_endpoint_rad')),
                         _roll(endpoint.get('final_pose_rad')) if endpoint.get('reported_settled') is True else None,
                         micro.get('hold')))
    return dict(schema='rocell.micro_result_summary.v1', legs=legs,
                status=report.get('status', 'UNAVAILABLE'),
                micro_result_present=micro is not None,
                measurement_source='CONTROLLER_JOINT_TELEMETRY',
                independently_verified=False, physical_accuracy_verified=False,
                motion_authorized=False)
