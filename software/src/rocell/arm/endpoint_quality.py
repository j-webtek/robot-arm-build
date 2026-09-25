"""Read-only quality projection, separate from immutable admission verdicts."""
import math


def assess_endpoint_quality(endpoint, *, final_joints, next_start_joints=None):
    """Label a proposed 0.1-degree precision screen without authorizing motion.

    Existing arrival/persistence decisions are copied, never recomputed with a
    tighter tolerance. One run cannot establish across-run repeatability.
    """
    def pose_ok(pose):
        return isinstance(pose,(list,tuple)) and len(pose)==6 and all(
            type(v) in (int,float) and math.isfinite(v) for v in pose)
    if not pose_ok(final_joints) or (next_start_joints is not None and not pose_ok(next_start_joints)):
        raise ValueError('Finite six-joint poses required')
    error=endpoint.get('final_error_rad')
    if type(error) not in (int,float) or not math.isfinite(error):
        raise ValueError('Finite endpoint error required')
    persistence=endpoint.get('persistence')
    arrival=persistence.get('full_window_endpoint',endpoint) if persistence else endpoint
    error_deg=abs(math.degrees(error))
    matches=None if next_start_joints is None else all(
        abs(a-b)<=math.radians(.01) for a,b in zip(final_joints,next_start_joints))
    return dict(schema='rocell.endpoint_quality.v1',basis='RECONSTRUCTED_CONTROLLER_REPORTS',
        historical_endpoint_verified=endpoint['endpoint_verified'],
        arrival_status='PASSED_EXISTING_CRITERIA' if arrival['endpoint_verified'] else 'NOT_PASSED',
        persistence_status=persistence['status'] if persistence else 'NOT_ASSESSED_35S',
        precision_status='WITHIN_DIAGNOSTIC_SCREEN' if error_deg<=.1 else 'OUTSIDE_DIAGNOSTIC_SCREEN',
        absolute_error_deg=error_deg,precision_screen_deg=.1,
        precision_screen_role='PROPOSED_DIAGNOSTIC_ONLY_NOT_ADMISSION_POLICY',
        repeatability_status='NOT_ASSESSED_FROM_SINGLE_TRIAL',
        next_start_status='NOT_SPECIFIED' if matches is None else 'REPORTED_MATCH' if matches else 'REPORTED_MISMATCH',
        next_start_tolerance_deg=.01,next_start_joints=next_start_joints,
        fresh_feedback_required=True,admission_policy_changed=False,
        physical_accuracy_verified=False,motion_authorized=False)
