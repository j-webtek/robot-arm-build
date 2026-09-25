"""Independently reconstruct fully evaluated native-path campaign records.

Native-path provenance stays unqualified. No signature, executable, process,
physical movement or stopping claim is inferred from a self-contained result.
Incomplete runs belong in diagnostic retention, not completed verification.
"""
from .first_motion_contract import canonical
from .positional_campaign_reconstruction import _verify_completed_campaign_records
from rocell.safety.positional_campaign_authority import PositionalCampaignIntent


def review_native_campaign(request, result):
    fields = {'schema', 'basis', 'intent_sha256', 'status', 'legs', 'errors', 'cleanup',
        'lifecycle', 'native_submission_attempts', 'native_execution_released',
        'physical_movement_verified', 'physical_stop_verified', 'replay_allowed', 'skipped_leg_ids'}
    if (type(request) is not PositionalCampaignIntent or type(result) is not dict
            or set(result) != fields or len(canonical(result)) > 2_097_152
            or result['schema'] != 'rocell.native_positional_campaign_trial.v1'
            or result['basis'] != 'NATIVE_PATH_UNQUALIFIED' or result['intent_sha256'] != request.sha256
            or result['status'] not in ('REPORTED_CAMPAIGN_COMPLETE', 'HELD')
            or any(result[key] is not False for key in ('native_execution_released',
                'physical_movement_verified', 'physical_stop_verified', 'replay_allowed'))
            or type(result['legs']) is not list or not 1 <= len(result['legs']) <= request.to_dict()['limits']['maximum_writes']):
        raise ValueError('Exact fully evaluated native campaign required')
    cleanup = result['cleanup']
    if (type(cleanup) is not dict or set(cleanup) != {'all_handles_closed', 'pending_io_count',
            'within_budget', 'started_ns', 'finished_ns'}
            or cleanup['all_handles_closed'] is not True or cleanup['within_budget'] is not True
            or type(cleanup['pending_io_count']) is not int or cleanup['pending_io_count'] != 0):
        raise ValueError('Clean native campaign cleanup required')
    # Normalize only the cleanup record shape. Keep the native completion label
    # and submission count; use exactly the same endpoint math and commit hashes.
    records = dict(result, cleanup=dict(status='HANDLES_CLOSED',
        started_ns=cleanup['started_ns'], finished_ns=cleanup['finished_ns']))
    checked = _verify_completed_campaign_records(request, records,
        complete_status='REPORTED_CAMPAIGN_COMPLETE', attempts_field='native_submission_attempts')
    expected_legs = []
    calls, counts = dict(baseline=0, post=0), dict(baseline=0, post=0)
    for record in result['legs']:
        leg_calls = {phase: record[phase]['read_calls'] for phase in calls}
        leg_bytes = {phase: record[phase]['raw']['bytes'] for phase in calls}
        for phase in calls:
            calls[phase] += leg_calls[phase]
            counts[phase] += leg_bytes[phase]
        expected_legs.append(dict(leg_id=record['leg_id'], submission_attempted=True,
            confirmed_write_bytes=record['write']['confirmed_bytes'],
            read_calls=leg_calls, read_bytes=leg_bytes))
    expected = dict(schema='rocell.positional_campaign_connection_lifecycle.v1', phase='CLOSED',
        request_sha256=request.sha256, connection_id=request.to_dict()['campaign_id'],
        owned_handle_count=0, pending_io_count=0, read_calls=calls, read_bytes=counts,
        confirmed_write_bytes=sum(leg['confirmed_write_bytes'] for leg in expected_legs),
        late_cleanup_read_base64='', errors=[], physical_stop_verified=False, legs=expected_legs)
    if canonical(result['lifecycle']) != canonical(expected):
        raise ValueError('Native lifecycle differs from original capture/write accounting')
    return dict(checked, native_process_verified=False, review_authenticity_verified=False,
        basis='NATIVE_PATH_UNQUALIFIED')
