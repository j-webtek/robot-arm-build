"""Compact child receipts and immutable parent retention for campaign attempts.

Missing or rejected evidence is diagnostic, never retry permission. Child trial
paths are derived from the immutable campaign ID, not supplied in child stdout.
No process is launched and no serial API is used by this module.
"""
import hashlib
import base64

from .first_motion_contract import canonical
from .physical_onboarding_durability import (
    PublicationMode, contained_path, publish_bytes, publish_reservation_bytes, read_bounded_regular_file, safe_root,
)
from .positional_campaign_launch import verify_campaign_claim_originals
from .positional_campaign_native_review import review_native_campaign
from .wizard_diagnostic_coordinator import decode_diagnostic_json
from rocell.safety.positional_campaign_authority import PositionalCampaignIntent
from rocell.providers.windows.owned_worker_process import OwnedWorkerResult, _hash
from rocell.providers.windows.positional_campaign_native_protocol import RESULT_SCHEMA, decode_request

MAX_TRIAL_BYTES = 2_097_152


def retain_native_trial(root, request, result, *, claim_sha256):
    if type(request) is not PositionalCampaignIntent or type(result) is not dict:
        raise ValueError('Exact native campaign trial required')
    _hash(claim_sha256)
    if (result.get('schema') != 'rocell.native_positional_campaign_trial.v1'
            or result.get('intent_sha256') != request.sha256
            or result.get('basis') != 'NATIVE_PATH_UNQUALIFIED'):
        raise ValueError('Native trial association mismatch')
    raw = canonical(result)
    name = request.to_dict()['campaign_id'] + '-native-trial.json'
    # The child cannot rename within its supervisor-pinned directory. Reserve
    # once and flush/read back before emitting the digest receipt. A crash tail
    # is invalid retained evidence, never an atomic success or retry permission.
    # Parent exports still use immutable publication after child cleanup.
    path = publish_reservation_bytes(safe_root(root), name, raw, maximum_bytes=MAX_TRIAL_BYTES)
    if read_bounded_regular_file(path, maximum_bytes=MAX_TRIAL_BYTES) != raw:
        raise ValueError('Native trial readback mismatch')
    return canonical(dict(schema=RESULT_SCHEMA, intent_sha256=request.sha256,
        claim_sha256=claim_sha256, trial_sha256=hashlib.sha256(raw).hexdigest(),
        trial_bytes=len(raw), physical_authority=False))


def publish_native_campaign_result(root, reader, *, request_original, receipt):
    return publish_campaign_process_result(root, reader.request,
        request_original=request_original, receipt=receipt)


def publish_campaign_process_result(root, request, *, request_original, receipt):
    """Retain even prelaunch failures, without needing a live device reader."""
    if type(receipt) is not OwnedWorkerResult or type(request_original) is not bytes:
        raise ValueError('Exact parent receipt and request original required')
    if type(request) is not PositionalCampaignIntent:
        raise ValueError('Exact campaign intent required')
    wire = decode_request(request_original)
    root = safe_root(root)
    if (wire['operation_sha256'] != request.sha256
            or safe_root(wire['payload']['root']) != root
            or receipt.attempt_id != request.to_dict()['campaign_id']
            or receipt.request_sha256 != wire['request_sha256']):
        raise ValueError('Parent campaign retention association mismatch')
    prefix = request.to_dict()['campaign_id'] + '-parent-'
    report = dict(schema='rocell.native_campaign_retained_result.v1',
        intent_sha256=request.sha256, status='DIAGNOSTIC_RETAINED', originals={},
        process=None, reconstruction=None, endpoint_reported_complete=False,
        native_execution_released=False, physical_movement_verified=False,
        physical_stop_verified=False, replay_allowed=False, errors=[])
    def retain(name, raw, maximum):
        if type(raw) is not bytes or len(raw) > maximum:
            raise ValueError('Campaign original exceeds retention budget')
        filename = prefix + name + '.original.json'
        stored = canonical(dict(bytes=len(raw), base64=base64.b64encode(raw).decode('ascii')))
        publish_bytes(root, filename, stored, mode=PublicationMode.IMMUTABLE,
            maximum_bytes=max(1024, min(4*1024*1024, maximum*2)))
        report['originals'][name] = dict(file=filename, encoding='base64-json',
            bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())
    # Preserve supervisor and IPC originals even if the child receipt is bad.
    retain('request', request_original, 65536)
    retain('stdout', receipt.stdout, 256*1024)
    retain('stderr', receipt.stderr, 8192)
    supervisor = receipt.to_dict()
    supervisor.pop('parsed_result', None)
    retain('supervisor', canonical(supervisor), 65536)
    for stage in ('launch', 'claimed'):
        try:
            path = contained_path(root, request.to_dict()['campaign_id'] + '-positional-' + stage + '.json',
                label='campaign process original')
            retain(stage, read_bounded_regular_file(path, maximum_bytes=65536), 65536)
        except (ValueError, OSError, RuntimeError) as error:
            report['errors'].append(dict(stage='retain_' + stage, code=type(error).__name__))
    try:
        child = decode_diagnostic_json(receipt.stdout, maximum=8192)
        fields = {'schema', 'intent_sha256', 'claim_sha256', 'trial_sha256', 'trial_bytes', 'physical_authority'}
        if (type(child) is not dict or set(child) != fields or child['schema'] != RESULT_SCHEMA
                or child['intent_sha256'] != request.sha256 or child['physical_authority'] is not False
                or type(child['trial_bytes']) is not int or not 0 < child['trial_bytes'] <= MAX_TRIAL_BYTES):
            raise ValueError('Exact compact campaign child receipt required')
        _hash(child['claim_sha256'])
        _hash(child['trial_sha256'])
        path = contained_path(root, request.to_dict()['campaign_id'] + '-native-trial.json', label='native trial')
        trial_raw = read_bounded_regular_file(path, maximum_bytes=MAX_TRIAL_BYTES)
        # Preserve the actual bytes seen by the parent even on a digest mismatch.
        retain('trial', trial_raw, MAX_TRIAL_BYTES)
        if len(trial_raw) != child['trial_bytes'] or hashlib.sha256(trial_raw).hexdigest() != child['trial_sha256']:
            raise ValueError('Native trial differs from child receipt')
        prefix_claim = request.to_dict()['campaign_id'] + '-positional-'
        launch_raw = read_bounded_regular_file(contained_path(root, prefix_claim+'launch.json', label='campaign launch original'), maximum_bytes=65536)
        claim_raw = read_bounded_regular_file(contained_path(root, prefix_claim+'claimed.json', label='campaign claim original'), maximum_bytes=8192)
        report['process'] = verify_campaign_claim_originals(request, request_original=request_original,
            claim_sha256=child['claim_sha256'], receipt=receipt, launch_raw=launch_raw, claim_raw=claim_raw)
        trial = decode_diagnostic_json(trial_raw, maximum=MAX_TRIAL_BYTES)
        reviewed = review_native_campaign(request, trial)
        if (type(receipt.elapsed_ns) is not int or receipt.elapsed_ns < 0
                or trial['legs'][0]['baseline']['started_ns'] < receipt.finished_monotonic_ns-receipt.elapsed_ns
                or trial['cleanup']['finished_ns'] > receipt.finished_monotonic_ns):
            raise ValueError('Native trial extends outside observed process lifetime')
        report['reconstruction'] = reviewed
        report['status'] = 'DATA_RECONSTRUCTED'
        report['endpoint_reported_complete'] = (report['process']['process_completion_verified']
            and report['reconstruction']['reconstructed_status'] == 'REPORTED_CAMPAIGN_COMPLETE')
    except (ValueError, OSError, RuntimeError, TypeError, KeyError, IndexError) as error:
        report['errors'].append(dict(stage='native_result_review', code=type(error).__name__))
    path = publish_bytes(root, prefix + 'report.json', canonical(report),
        mode=PublicationMode.IMMUTABLE, maximum_bytes=65536)
    return path, report
