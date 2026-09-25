"""Original-bound, one-use campaign launch records; no process or device APIs.

The authenticated reader must be composed internally. A claim only accounts for
one process attempt; it does not approve executable files, a serial open, or any
leg. Those independent native boundaries must still be implemented and checked.
"""
import hashlib
import os
from threading import Lock

from .first_motion_contract import canonical
from .physical_onboarding_durability import (
    contained_path, publish_reservation_bytes, read_bounded_regular_file, safe_root,
)
from .wizard_diagnostic_coordinator import decode_diagnostic_json
from rocell.providers.windows.positional_current_context import AuthenticatedPositionalReader

_ISSUER = object()


def _path(root, reader, stage):
    if type(reader) is not AuthenticatedPositionalReader or stage not in ('launch', 'claimed'):
        raise ValueError('Exact authenticated campaign reader required')
    return contained_path(safe_root(root), reader.request.to_dict()['campaign_id']
        + '-positional-' + stage + '.json', label='campaign launch record')


def _read(root, reader, stage):
    raw = read_bounded_regular_file(_path(root, reader, stage), maximum_bytes=65536)
    body = decode_diagnostic_json(raw, maximum=65536)
    if type(body) is not dict or canonical(body) != raw:
        raise ValueError('Canonical campaign launch record required')
    return raw, body


def reserve_campaign_launch(root, reader, *, runtime_original):
    path = _path(root, reader, 'launch')
    if type(runtime_original) is not bytes:
        raise ValueError('Immutable runtime original required')
    runtime = decode_diagnostic_json(runtime_original, maximum=32768)
    if (type(runtime) is not dict or canonical(runtime) != runtime_original
            or hashlib.sha256(runtime_original).hexdigest()
                != reader.request.to_dict()['references']['runtime_sha256']):
        raise ValueError('Campaign runtime original differs from review')
    evidence = reader.verify_endpoint()
    reader.request.require_start_time(evidence['verified_at_ns'])
    raw = canonical(dict(schema='rocell.positional_launch.v1',
        intent=reader.request.to_dict(), runtime=runtime,
        review_bundle_sha256=evidence['bundle_sha256'], port_name=evidence['port_name'],
        reserved_ns=evidence['verified_at_ns'], process_may_have_started=True,
        replay_allowed=False, motion_authorized=False))
    publish_reservation_bytes(root, path.name, raw, maximum_bytes=65536)
    if _read(root, reader, 'launch')[0] != raw:
        raise ValueError('Campaign launch readback failed')
    return hashlib.sha256(raw).hexdigest()


def _verify_launch(root, reader, digest):
    raw, body = _read(root, reader, 'launch')
    evidence = reader.verify_endpoint()
    reader.request.require_start_time(evidence['verified_at_ns'])
    fields = {'schema', 'intent', 'runtime', 'review_bundle_sha256', 'port_name',
        'reserved_ns', 'process_may_have_started', 'replay_allowed', 'motion_authorized'}
    if (set(body) != fields or body['schema'] != 'rocell.positional_launch.v1'
            or hashlib.sha256(raw).hexdigest() != digest
            or canonical(body['intent']) != reader.request.canonical_bytes
            or hashlib.sha256(canonical(body['runtime'])).hexdigest()
                != reader.request.to_dict()['references']['runtime_sha256']
            or body['review_bundle_sha256'] != evidence['bundle_sha256']
            or body['port_name'] != evidence['port_name']
            or type(body['reserved_ns']) is not int
            or not reader.request.to_dict()['issued_ns'] <= body['reserved_ns'] <= evidence['verified_at_ns']
            or body['process_may_have_started'] is not True
            or body['replay_allowed'] is not False or body['motion_authorized'] is not False):
        raise ValueError('Campaign launch context changed')
    return evidence


class CampaignWorkerClaim:
    def __init__(self, issuer, root, reader, launch_sha256, raw):
        if issuer is not _ISSUER:
            raise ValueError('Campaign claim factory required')
        self._root, self._reader, self._launch, self._raw = root, reader, launch_sha256, raw
        self._pid, self._used, self._lock = os.getpid(), False, Lock()

    @property
    def claim_sha256(self):
        return hashlib.sha256(self._raw).hexdigest()

    def consume(self):
        with self._lock:
            if self._used:
                raise ValueError('Campaign worker claim consumed')
            self._used = True  # Failed checks also burn this in-process claim.
            if os.getpid() != self._pid:
                raise ValueError('Campaign worker process changed')
            _verify_launch(self._root, self._reader, self._launch)
            if _read(self._root, self._reader, 'claimed')[0] != self._raw:
                raise ValueError('Campaign worker claim original changed')


def claim_campaign_worker(root, reader, *, launch_sha256):
    evidence = _verify_launch(root, reader, launch_sha256)
    raw = canonical(dict(schema='rocell.positional_worker_claim.v1',
        intent_sha256=reader.request.sha256, launch_sha256=launch_sha256,
        pid=os.getpid(), claimed_ns=evidence['verified_at_ns'],
        replay_allowed=False, motion_authorized=False))
    publish_reservation_bytes(root, _path(root, reader, 'claimed').name, raw, maximum_bytes=8192)
    if _read(root, reader, 'claimed')[0] != raw:
        raise ValueError('Campaign worker claim readback failed')
    return CampaignWorkerClaim(_ISSUER, safe_root(root), reader, launch_sha256, raw)


def verify_campaign_claim_receipt(root, reader, *, request_original, claim_sha256, receipt):
    """Parent-only association of stored claims with its actual process receipt.

    Never re-resolve/open a device or renew an expired request after execution.
    This does not authenticate the review anew, validate child result data, prove
    claim consumption, or establish serial cleanup. Those layers stay separate.
    """
    from rocell.providers.windows.owned_worker_process import OwnedWorkerResult
    from rocell.providers.windows.positional_campaign_native_protocol import decode_request
    if type(receipt) is not OwnedWorkerResult or type(request_original) is not bytes:
        raise ValueError('Exact parent process receipt and request bytes required')
    wire = decode_request(request_original)
    if safe_root(wire['payload']['root']) != safe_root(root):
        raise ValueError('Campaign parent root mismatch')
    launch_raw, _ = _read(root, reader, 'launch')
    claim_raw, _ = _read(root, reader, 'claimed')
    return verify_campaign_claim_originals(reader.request, request_original=request_original,
        claim_sha256=claim_sha256, receipt=receipt, launch_raw=launch_raw, claim_raw=claim_raw)


def verify_campaign_claim_originals(request, *, request_original, claim_sha256, receipt, launch_raw, claim_raw):
    """Pure association check for parent-retained originals, with no path access.

    When used off-host this proves consistency, not authenticity of a supplied
    process receipt. Its caller must keep that distinction in the exported UI.
    """
    from rocell.safety.positional_campaign_authority import PositionalCampaignIntent
    from rocell.providers.windows.owned_worker_process import OwnedWorkerResult
    from rocell.providers.windows.positional_campaign_native_protocol import decode_request
    if (type(request) is not PositionalCampaignIntent or type(receipt) is not OwnedWorkerResult
            or any(type(raw) is not bytes for raw in (request_original, launch_raw, claim_raw))):
        raise ValueError('Exact campaign process originals required')
    wire = decode_request(request_original)
    launch = decode_diagnostic_json(launch_raw, maximum=65536)
    claim = decode_diagnostic_json(claim_raw, maximum=8192)
    if (type(launch) is not dict or type(claim) is not dict
            or canonical(launch) != launch_raw or canonical(claim) != claim_raw):
        raise ValueError('Canonical campaign process originals required')
    intent = request.to_dict()
    if (wire['operation_sha256'] != request.sha256
            or receipt.request_sha256 != wire['request_sha256']
            or receipt.attempt_id != intent['campaign_id']
            or type(receipt.owned_process_id) is not int or not 0 < receipt.owned_process_id < 2**32
            or type(receipt.finished_monotonic_ns) is not int
            or not 0 < receipt.finished_monotonic_ns < 2**63
            or hashlib.sha256(launch_raw).hexdigest() != wire['payload']['launch_sha256']
            or canonical(launch.get('intent')) != request.canonical_bytes
            or canonical(launch.get('runtime')) != canonical(wire['payload']['registration'])
            or set(claim) != {'schema', 'intent_sha256', 'launch_sha256', 'pid', 'claimed_ns',
                'replay_allowed', 'motion_authorized'}
            or claim['schema'] != 'rocell.positional_worker_claim.v1'
            or hashlib.sha256(claim_raw).hexdigest() != claim_sha256
            or claim['intent_sha256'] != request.sha256
            or claim['launch_sha256'] != wire['payload']['launch_sha256']
            or type(claim['pid']) is not int or claim['pid'] != receipt.owned_process_id
            or type(claim['claimed_ns']) is not int or type(launch.get('reserved_ns')) is not int
            or not intent['issued_ns'] <= launch['reserved_ns'] <= claim['claimed_ns'] <= receipt.finished_monotonic_ns
            or claim['replay_allowed'] is not False or claim['motion_authorized'] is not False):
        raise ValueError('Campaign parent receipt or stored claim mismatch')
    request.require_start_time(launch['reserved_ns'])
    request.require_start_time(claim['claimed_ns'])
    complete = (receipt.status == 'SUCCEEDED' and receipt.primary_error is None
        and receipt.cleanup_errors == () and receipt.process_created is True
        and receipt.initial_thread_resumed is True and receipt.tree_exit_confirmed is True
        and type(receipt.returncode) is int and receipt.returncode == 0
        and type(receipt.stdin_bytes_written) is int and receipt.stdin_bytes_written == len(request_original)
        and type(receipt.elapsed_ns) is int and receipt.elapsed_ns >= 0
        and intent['issued_ns'] <= receipt.finished_monotonic_ns - receipt.elapsed_ns <= claim['claimed_ns']
        and receipt.finished_monotonic_ns <= intent['deadline_ns'])
    return dict(claim_receipt_association_verified=True,
        process_completion_verified=complete, claim_sha256=claim_sha256,
        owned_process_id=receipt.owned_process_id, serial_cleanup_verified=False,
        endpoint_verified=False, review_authenticity_verified=False,
        physical_stop_verified=False, motion_authorized=False, replay_allowed=False)
