"""Read-only reanalysis of a named, verified workspace diagnostic export."""

import base64
import hashlib
import re

from rocell.arm.telemetry_coverage import analyze_window_coverage
from .physical_onboarding_durability import read_bounded_regular_file
from .wizard_diagnostic_coordinator import decode_diagnostic_json
from .wizard_diagnostic_export import verify_export

LOG_NAME = 'attachment-powered-feedback-native-logs.json'


def validate_export_name(name):
    if type(name) is not str or re.fullmatch(r'wizard-\d{8}T\d{12}Z-[a-f0-9]{32}', name) is None:
        raise ValueError('Use an exact wizard export folder name, not a path')
    return name


def reanalyze_logs(payload: bytes):
    """Reconstruct hash-bound worker output and decode all retained capture bytes.

    Hashes show byte consistency, not trusted device origin or current freshness.
    No earlier capped parser count or stored pose is used as analysis input.
    """
    logs = decode_diagnostic_json(payload, maximum=1024*1024)
    if logs.get('schema') != 'rocell.powered_feedback_native_logs.v1' or logs.get('physical_authority') is not False:
        raise ValueError('Unsupported retained native log schema')
    chunks = logs.get('stdout_base64_chunks')
    if type(chunks) is not list or len(chunks) > 256 or any(type(c) is not str for c in chunks):
        raise ValueError('Invalid retained stdout chunks')
    if sum(map(len, chunks)) > 350000:
        raise ValueError('Retained stdout exceeds analysis budget')
    stdout = b''.join(base64.b64decode(chunk, validate=True) for chunk in chunks)
    process = logs['process']
    if (type(process.get('stdout_bytes')) is not int or process['stdout_bytes'] != len(stdout)
            or process.get('stdout_sha256') != hashlib.sha256(stdout).hexdigest()):
        raise ValueError('Worker stdout original mismatch')
    result = decode_diagnostic_json(stdout, maximum=262144)
    if (result.get('schema') != 'rocell.owned_powered_feedback_native_result.v1'
            or result.get('physical_authority') is not False
            or result.get('attempt_id') != process.get('attempt_id')
            or result.get('request_sha256') != process.get('request_sha256')):
        raise ValueError('Worker identity/schema mismatch')
    child = result['child_result']
    observation = child['observation']
    if (child.get('schema') != 'rocell.powered_feedback_native_child_result.v1'
            or observation.get('schema') not in {'rocell.powered_telemetry_observation.v2', 'rocell.powered_telemetry_observation.v3'}
            or type(observation.get('request_sha256')) is not str
            or re.fullmatch(r'[a-f0-9]{64}', observation['request_sha256']) is None
            or observation.get('physical_authority') is not False):
        raise ValueError('Timed observation schema/context mismatch')
    original = observation['capture']['raw']
    if type(original.get('base64')) is not str or len(original['base64']) > 87384:
        raise ValueError('Capture byte budget exceeded')
    raw = base64.b64decode(original['base64'], validate=True)
    if (type(original.get('bytes')) is not int or original['bytes'] != len(raw)
            or original.get('sha256') != hashlib.sha256(raw).hexdigest()):
        raise ValueError('Capture original mismatch')
    coverage = analyze_window_coverage(raw, observation['read_windows'], display_limit=0)
    return {'schema': 'rocell.wizard_saved_capture_analysis.v1',
            'basis': 'OFFLINE_REANALYSIS_OF_RETAINED_EXPORT',
            'attempt_id': process['attempt_id'], 'request_sha256': result['request_sha256'],
            'observation_intent_sha256': observation['request_sha256'],
            'source_log_sha256': hashlib.sha256(payload).hexdigest(),
            'worker_stdout_sha256': process['stdout_sha256'],
            'recorded_origin': observation.get('origin'), 'recorded_capture_status': observation.get('status'),
            'coverage': coverage,
            # Keep every original byte without exceeding the wizard's bounded
            # per-string retention policy. Decode each chunk independently.
            'retained_original': {'bytes':len(raw), 'sha256':original['sha256'],
                'base64_chunks':[base64.b64encode(raw[i:i+768]).decode('ascii') for i in range(0,len(raw),768)]},
            'read_windows': observation['read_windows'],
            'sample_freshness_verified': False, 'motion_authorized': False, 'physical_authority': False,
            'message': 'Historical capture only. Parsing completeness is not current connection, freshness, calibration or movement qualification.'}


def run_saved_capture(workspace, export_name):
    name = validate_export_name(export_name)
    folder = workspace / 'software/runs/wizard-exports' / name
    verified = verify_export(folder)
    if verified.get('valid') is not True:
        raise ValueError('Selected diagnostic export did not pass manifest verification')
    descriptor = next((item for item in verified['files'] if item['name'] == LOG_NAME), None)
    if descriptor is None:
        raise ValueError('Selected export has no retained powered-feedback native logs')
    payload = read_bounded_regular_file(folder / LOG_NAME, maximum_bytes=1024*1024, label='saved telemetry logs')
    if len(payload) != descriptor['bytes'] or hashlib.sha256(payload).hexdigest() != descriptor['sha256']:
        raise ValueError('Selected log changed after manifest verification')
    report = reanalyze_logs(payload)
    report['source_export'] = {'name': name, 'manifest_sha256': verified['manifest_sha256']}
    return report
