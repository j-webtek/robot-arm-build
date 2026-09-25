"""Read-only portable verification of a parent-retained native campaign bundle.

Reproduces consistency from exported originals. It does not authenticate an
off-host process receipt, read the original workcell, or grant motion authority.
"""
import base64
from dataclasses import fields
import hashlib
import re

from .first_motion_contract import canonical
from .physical_onboarding_durability import contained_path, read_bounded_regular_file, safe_root
from .positional_campaign_launch import verify_campaign_claim_originals
from .positional_campaign_native_review import review_native_campaign
from .wizard_diagnostic_coordinator import decode_diagnostic_json
from rocell.providers.windows.owned_worker_process import OwnedWorkerResult
from rocell.providers.windows.positional_campaign_native_protocol import decode_request, RESULT_SCHEMA
from rocell.safety.positional_campaign_authority import PositionalCampaignIntent, campaign_joint_index, BASE_SCHEMAS, SYNCHRONIZED_SCHEMAS, ROLL_SCHEMAS
from rocell.arm.campaign_stream_sync import campaign_window, campaign_post_window, FRAMED_SCHEMAS
from rocell.arm.first_motion_analysis import _window
from .positional_campaign_capture import validate_campaign_capture

LIMITS = dict(request=65536, stdout=256*1024, stderr=8192, supervisor=65536,
    launch=65536, claimed=65536, trial=2_097_152)


def verify_native_retained_export(directory, report_name):
    root = safe_root(directory)
    if type(report_name) is not str or not re.fullmatch('campaign-[a-f0-9]{32}-parent-report.json', report_name):
        raise ValueError('Exact campaign report filename required')
    report_raw = read_bounded_regular_file(contained_path(root, report_name, label='campaign report'), maximum_bytes=65536)
    report = decode_diagnostic_json(report_raw, maximum=65536)
    expected_fields = {'schema', 'intent_sha256', 'status', 'originals', 'process', 'reconstruction',
        'endpoint_reported_complete', 'native_execution_released', 'physical_movement_verified',
        'physical_stop_verified', 'replay_allowed', 'errors'}
    if (type(report) is not dict or set(report) != expected_fields
            or canonical(report) != report_raw or report['schema'] != 'rocell.native_campaign_retained_result.v1'
            or any(report[key] is not False for key in ('native_execution_released',
                'physical_movement_verified', 'physical_stop_verified', 'replay_allowed'))
            or type(report['originals']) is not dict
            or not {'request', 'stdout', 'stderr', 'supervisor'} <= set(report['originals']) <= set(LIMITS)):
        raise ValueError('Exact retained campaign report required')
    originals = {}
    for name, item in report['originals'].items():
        expected_name = report_name.removesuffix('report.json') + name + '.original.json'
        if (type(item) is not dict or set(item) != {'file', 'encoding', 'bytes', 'sha256'}
                or item['file'] != expected_name or item['encoding'] != 'base64-json'
                or type(item['bytes']) is not int or not 0 <= item['bytes'] <= LIMITS[name]):
            raise ValueError('Bounded exact original reference required')
        maximum = max(1024, min(4*1024*1024, LIMITS[name]*2))
        encoded = read_bounded_regular_file(contained_path(root, expected_name, label='campaign original'), maximum_bytes=maximum)
        wrapper = decode_diagnostic_json(encoded, maximum=maximum)
        if type(wrapper) is not dict or set(wrapper) != {'bytes', 'base64'} or canonical(wrapper) != encoded:
            raise ValueError('Exact campaign byte wrapper required')
        raw = base64.b64decode(wrapper['base64'], validate=True)
        if (type(wrapper['bytes']) is not int or len(raw) != wrapper['bytes'] or len(raw) != item['bytes']
                or hashlib.sha256(raw).hexdigest() != item['sha256']):
            raise ValueError('Campaign original size or digest changed')
        originals[name] = raw
    wire = decode_request(originals['request'])
    request = PositionalCampaignIntent(canonical(wire['payload']['campaign_intent']))
    if (request.sha256 != report['intent_sha256']
            or report_name != request.to_dict()['campaign_id'] + '-parent-report.json'):
        raise ValueError('Campaign report/request association changed')
    saved = decode_diagnostic_json(originals['supervisor'], maximum=65536)
    if type(saved) is not dict or type(saved.get('cleanup_errors')) is not list:
        raise ValueError('Stored supervisor receipt required')
    kwargs = {field.name: saved[field.name] for field in fields(OwnedWorkerResult)
        if field.name not in ('stdout', 'stderr', 'parsed_result')}
    kwargs['cleanup_errors'] = tuple(kwargs['cleanup_errors'])
    receipt = OwnedWorkerResult(**kwargs, stdout=originals['stdout'], stderr=originals['stderr'])
    reproduced = receipt.to_dict()
    reproduced.pop('parsed_result', None)
    if canonical(reproduced) != canonical(saved):
        raise ValueError('Supervisor receipt differs from IPC originals')
    process = reconstruction = None
    try:
        child = decode_diagnostic_json(originals['stdout'], maximum=8192)
        if (type(child) is not dict or set(child) != {'schema', 'intent_sha256', 'claim_sha256',
                'trial_sha256', 'trial_bytes', 'physical_authority'} or child['schema'] != RESULT_SCHEMA
                or child['intent_sha256'] != request.sha256 or child['physical_authority'] is not False
                or type(child['trial_bytes']) is not int or child['trial_bytes'] != len(originals['trial'])
                or hashlib.sha256(originals['trial']).hexdigest() != child['trial_sha256']):
            raise ValueError('Child trial association differs')
        process = verify_campaign_claim_originals(request, request_original=originals['request'],
            claim_sha256=child['claim_sha256'], receipt=receipt,
            launch_raw=originals['launch'], claim_raw=originals['claimed'])
        trial = decode_diagnostic_json(originals['trial'], maximum=LIMITS['trial'])
        checked = review_native_campaign(request, trial)
        if (type(receipt.elapsed_ns) is not int or receipt.elapsed_ns < 0
                or trial['legs'][0]['baseline']['started_ns'] < receipt.finished_monotonic_ns-receipt.elapsed_ns
                or trial['cleanup']['finished_ns'] > receipt.finished_monotonic_ns):
            raise ValueError('Trial outside process lifetime')
        reconstruction = checked
    except (ValueError, TypeError, KeyError, IndexError):
        pass  # Original failed/partial evidence remains a reproducible diagnostic.
    complete = bool(process and reconstruction and process['process_completion_verified']
        and reconstruction['reconstructed_status'] == 'REPORTED_CAMPAIGN_COMPLETE')
    status = 'DATA_RECONSTRUCTED' if reconstruction else 'DIAGNOSTIC_RETAINED'
    if (canonical(report['process']) != canonical(process)
            or canonical(report['reconstruction']) != canonical(reconstruction)
            or report['endpoint_reported_complete'] is not complete or report['status'] != status):
        raise ValueError('Stored native result claims differ from reproduction')
    # Derive the review table only after independent reconstruction succeeds.
    # This is a returned projection, not a change to immutable export formats.
    # Partial/unverified trials keep their raw evidence but get no invented
    # endpoint or settling estimate in this trusted summary.
    from rocell.arm.endpoint_quality import assess_endpoint_quality
    from rocell.safety.positional_campaign_authority import ROLL_LONG_FIXED_SCHEMA, ROLL_FRAMED_SCHEMA, roll_long_fixed_configuration
    from rocell.safety.positional_campaign_authority import ROLL_VARIATION_SCHEMA, roll_variation_configuration
    endpoints = []
    if reconstruction is not None:
        records = {record['leg_id']: record for record in trial['legs']}
        for leg in request.to_dict()['legs']:
            row = dict(leg_id=leg['leg_id'], command=leg['command'], target_rad=leg['target_rad'],
                status='NOT_EXECUTED', start_rad=None, final_rad=None, signed_error_rad=None,
                direction=None, write_finished_ns=None, quiet_entry_after_write_bounds_ns=None,
                post_sample_count=0, reported_endpoint_verified=False)
            record = records.get(leg['leg_id'])
            if record is not None:
                def rows(capture, phase):
                    raw = validate_campaign_capture(request, capture, phase=phase,
                        command_completed_ns=record['write']['finished_ns'] if phase == 'post' else None)
                    if phase=='post' and request.to_dict()['schema'] in FRAMED_SCHEMAS:
                        baseline=record['baseline']
                        before_raw=validate_campaign_capture(request,baseline,phase='baseline')
                        values,issues,framing=campaign_post_window(request.to_dict(),raw,capture['read_windows'],
                            capture['started_ns'],capture['finished_ns'],baseline_raw=before_raw,
                            baseline_windows=baseline['read_windows'],
                            write_started_ns=record['write']['started_ns'],write_finished_ns=record['write']['finished_ns'])
                        row['cross_window_framing']=framing
                    else:
                        values,issues,framing=campaign_window(request.to_dict(),phase,raw, capture['read_windows'], capture['started_ns'], capture['finished_ns'],
                            maximum_bytes=request.to_dict()['limits']['maximum_raw_bytes_per_leg'])
                    if phase=='baseline' and request.to_dict()['schema'] in SYNCHRONIZED_SCHEMAS:
                        row['baseline_synchronization']=framing
                    return values
                before, after = rows(record['baseline'], 'baseline'), rows(record['post'], 'post')
                axis=campaign_joint_index(request.to_dict())
                start, final = before[-1][2][axis], after[-1][2][axis]
                endpoint = record['verification']['endpoint']
                finished = record['write']['finished_ns']
                quiet = endpoint['quiet_dwell_entry_bounds_ns']
                row.update(status=endpoint['status'], start_rad=start, final_rad=final,
                    signed_error_rad=endpoint['final_error_rad'],
                    direction='INCREASING' if leg['target_rad'] > start else 'DECREASING' if leg['target_rad'] < start else 'UNCHANGED',
                    write_finished_ns=finished,
                    quiet_entry_after_write_bounds_ns=None if quiet is None else [value-finished for value in quiet],
                    post_sample_count=len(after), reported_endpoint_verified=endpoint['endpoint_verified'])
                if 'correction' in endpoint:
                    row['correction']=endpoint['correction']
                if 'persistence' in endpoint:
                    row['persistence']=endpoint['persistence']
                next_start=None
                if request.to_dict()['schema'] in (ROLL_LONG_FIXED_SCHEMA,ROLL_FRAMED_SCHEMA):
                    # This is a comparison with the opposite frozen profile,
                    # not a new command, admission or fabricated fresh baseline.
                    opposite='DECREASING' if row['direction']=='INCREASING' else 'INCREASING'
                    next_start=list(request.to_dict()['start_joints_rad'])
                    next_start[4]=roll_long_fixed_configuration(opposite)['expected_roll_start_rad']
                if request.to_dict()['schema']==ROLL_VARIATION_SCHEMA:
                    case_id=request.to_dict()['roll_probe']['case_id']
                    next_id='nominal' if case_id.startswith('return-') else 'return-'+case_id
                    next_start=roll_variation_configuration(next_id)['expected_start_joints_rad']
                    row['roll_case_id']=case_id
                row['quality_assessment']=assess_endpoint_quality(endpoint,
                    final_joints=after[-1][2],next_start_joints=next_start)
            endpoints.append(row)
            if request.to_dict()['schema'] in BASE_SCHEMAS:
                row['selected_joint']='b'
            if request.to_dict()['schema'] in ROLL_SCHEMAS:
                row['selected_joint']='r'
    return dict(valid=True, report_sha256=hashlib.sha256(report_raw).hexdigest(),
        originals_verified=len(originals), reconstruction_consistent=reconstruction is not None,
        endpoint_completion_consistent=complete, process_receipt_authenticated=False,
        physical_accuracy_verified=False, physical_stop_verified=False, motion_authorized=False,
        endpoint_diagnostics=endpoints, endpoint_diagnostics_basis='RECONSTRUCTED_CONTROLLER_REPORTS',
        configuration_references=request.to_dict()['references'])
