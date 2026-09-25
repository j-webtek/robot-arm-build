"""Reconstruct saved native evidence before a separate qualification review.

Hashes and parsed receipts are not authentication of a historical parent process.
This offline reader never qualifies physical motion or permits another command.
"""
import base64
import hashlib
import re

from .first_motion_contract import FirstMotionRequest, canonical
from .physical_onboarding_durability import contained_path, read_bounded_regular_file
from .wizard_diagnostic_coordinator import decode_diagnostic_json
from rocell.providers.windows.first_motion_native_protocol import decode_request, validate_payload
from rocell.providers.windows.first_motion_native_result import decode_result, validate_result, MAX_RESULT_BYTES


def readback_first_motion_result(root, request, *, expected_report_sha256, owned_result=None):
    """Select fixed filenames and recompute native analysis from raw streams.

    Failed publication remains failed even if its child bytes look plausible.
    No current source/power/connection is inferred from historical originals.
    """
    if (type(request) is not FirstMotionRequest or type(expected_report_sha256) is not str
            or not re.fullmatch(r'[a-f0-9]{64}', expected_report_sha256)):
        raise ValueError('Exact request and host-selected report digest required')
    prefix = request.to_dict()['attempt_id']+'-first_motion-'
    def read(name, limit):
        return read_bounded_regular_file(contained_path(root, prefix+name, label='native trial original'), maximum_bytes=limit)
    raw_report = read('report.json', MAX_RESULT_BYTES)
    if hashlib.sha256(raw_report).hexdigest() != expected_report_sha256:
        raise ValueError('Selected native result changed')
    report = decode_diagnostic_json(raw_report, maximum=MAX_RESULT_BYTES)
    if (type(report) is not dict or report.get('schema') != 'rocell.first_motion_retained_result.v1'
            or report.get('request_sha256') != request.request_sha256
            or report.get('status') not in ('RESULT_RETAINED','RESULT_REJECTED','PROCESS_COMPLETION_UNCONFIRMED')
            or any(report.get(key) is not False for key in ('physical_movement_verified','physical_stop_verified','campaign_advance_allowed','replay_allowed'))
            or type(report.get('originals')) is not dict or set(report['originals']) != {'request.json','stdout.bin','stderr.bin'}):
        raise ValueError('Diagnostic-only native result report required')
    streams = {}
    for name, limit in (('request.json',65536), ('stdout.bin',MAX_RESULT_BYTES), ('stderr.bin',8192)):
        wrapped = decode_diagnostic_json(read(name+'.original.json', 2*MAX_RESULT_BYTES), maximum=2*MAX_RESULT_BYTES)
        if (type(wrapped) is not dict or set(wrapped) != {'bytes','base64'}
                or type(wrapped['bytes']) is not int or type(wrapped['base64']) is not str
                or len(wrapped['base64']) > 4*((limit+2)//3)):
            raise ValueError('Bounded original stream wrapper required')
        raw = base64.b64decode(wrapped['base64'], validate=True)
        if (len(raw) > limit or wrapped['bytes'] != len(raw) or report['originals'][name] != dict(
                file=prefix+name+'.original.json', bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())):
            raise ValueError('Original stream bytes or fixed filename changed')
        streams[name] = raw
    wire = decode_request(streams['request.json'])
    retained_request = validate_payload(wire['payload'])
    if retained_request.canonical_bytes != request.canonical_bytes:
        raise ValueError('Native request does not match selected trial')
    summary = None
    if report['status'] != 'RESULT_REJECTED':
        value = decode_result(streams['stdout.bin'], wire=wire)
        summary = validate_result(value, wire=wire)
        if canonical(summary) != canonical(report.get('summary')):
            raise ValueError('Saved native summary differs from raw recomputation')
    ready = (report['status'] == 'RESULT_RETAINED' and report.get('claim_receipt_verified') is True
        and type(report.get('returncode')) is int and report['returncode'] == 0
        and report.get('process_tree_closed') is True and report.get('errors') == []
        and summary is not None and summary['status'] == 'COMPLETED_DATA_CONSISTENT'
        and summary['execution_status'] == 'REPORTED_WRIST_RESPONSE_REVIEW_REQUIRED')
    associated = False
    if owned_result is not None:
        from rocell.providers.windows.owned_worker_process import OwnedWorkerResult
        from .first_motion_worker_claim import verify_first_motion_worker_receipt
        if (type(owned_result) is not OwnedWorkerResult
                or owned_result.attempt_id != request.to_dict()['attempt_id']
                or owned_result.request_sha256 != wire['request_sha256']
                or owned_result.stdout != streams['stdout.bin'] or owned_result.stderr != streams['stderr.bin']):
            raise ValueError('Retained streams do not match the host-owned supervisor result')
        clean = (owned_result.status == 'SUCCEEDED' and owned_result.primary_error is None
            and owned_result.cleanup_errors == () and owned_result.process_created is True
            and owned_result.initial_thread_resumed is True and owned_result.tree_exit_confirmed is True
            and type(owned_result.returncode) is int and owned_result.returncode == 0
            and type(owned_result.stdin_bytes_written) is int
            and owned_result.stdin_bytes_written == len(streams['request.json']))
        if clean and summary is not None:
            verify_first_motion_worker_receipt(wire['payload']['root'], request,
                claim_sha256=summary['claim_sha256'], launch_sha256=wire['payload']['launch_sha256'],
                owned_process_id=owned_result.owned_process_id,
                runtime_sha256=hashlib.sha256(canonical(wire['payload']['registration'])).hexdigest(),
                finished_ns=owned_result.finished_monotonic_ns)
            associated = True
    return dict(schema='rocell.first_motion_native_readback.v1',
        request_sha256=request.request_sha256, report_sha256=expected_report_sha256,
        retained_status=report['status'], reconstructed_summary=summary,
        telemetry_ready_for_review=ready, owned_process_reauthenticated=False,
        owned_process_association_verified=associated,
        physical_movement_verified=False, campaign_advance_allowed=False,
        limitations=['Historical parent claims still require trusted host association.',
                     'Independent observation and an explicit qualification decision remain required.'])
