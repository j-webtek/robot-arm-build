"""Correlate evidence for explicit functional-response qualification review.

Callers select original receipts and the actual owned supervisor result. A ready
assessment is not a qualification decision, accuracy measurement or motion permit.
"""
from .first_motion_observation import load_observation
from .first_motion_result_readback import readback_first_motion_result


def assess_first_motion_evidence(request, *, result_root, observation_root,
                                 observation_receipt, owned_result):
    """Re-read both evidence chains; retain uncertainty instead of inferring it."""
    if type(observation_receipt) is not dict:
        raise ValueError('Host-selected observation receipt required')
    observation = load_observation(request, root=observation_root,
        operation_id=observation_receipt['operation_id'],
        expected_observation_sha256=observation_receipt['observation_sha256'],
        expected_result_sha256=observation_receipt['result_sha256'])
    native = readback_first_motion_result(result_root, request,
        expected_report_sha256=observation_receipt['result_sha256'], owned_result=owned_result)
    holds = []
    if not native['telemetry_ready_for_review']: holds.append('TELEMETRY_NOT_READY')
    if not native['owned_process_association_verified']: holds.append('OWNED_PROCESS_NOT_ASSOCIATED')
    if observation['reported']['outcome'] != 'EXPECTED_MOVEMENT': holds.append('OBSERVATION_NOT_EXPECTED_MOVEMENT')
    if observation['reported']['coverage'] != 'ENTIRE_TRIAL': holds.append('OBSERVATION_COVERAGE_INCOMPLETE')
    return dict(schema='rocell.first_motion_qualification_assessment.v1',
        attempt_id=request.to_dict()['attempt_id'], request_sha256=request.request_sha256,
        result_sha256=observation_receipt['result_sha256'],
        observation_sha256=observation_receipt['observation_sha256'],
        status='HELD' if holds else 'READY_FOR_EXPLICIT_QUALIFICATION_REVIEW', holds=holds,
        native_readback=native, reported_observation=observation['reported'],
        physical_movement_verified=False, physical_accuracy_verified=False,
        physical_stop_verified=False, campaign_advance_allowed=False,
        limitations=['Observer identity, method compliance and event timing require explicit review.',
                     'Agreement is not calibrated accuracy or qualification of other poses, speeds or payloads.',
                     'A subsequent trial always requires its own current checks and one-use permission.'])
