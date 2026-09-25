"""Durable absolute diagnostic launch and one-use process claims; no device IO.

Hash association is not executable approval. The supervisor must separately
verify executable/package originals and bind its observed process receipt.
"""
import hashlib
import os
from threading import Lock

from rocell.safety.absolute_wrist_review_authority import AbsoluteWristIntent
from .first_motion_contract import canonical
from .physical_onboarding_durability import (
    safe_root, contained_path, publish_reservation_bytes, read_bounded_regular_file,
)
from .wizard_diagnostic_coordinator import decode_diagnostic_json

_ISSUER = object()


def _path(root, request, stage):
    if type(request) is not AbsoluteWristIntent or stage not in ('launch', 'claimed', 'reviews'):
        raise ValueError('Exact absolute worker record required')
    return contained_path(safe_root(root), request.to_dict()['attempt_id'] +
                          '-absolute-wrist-' + stage + '.json', label='absolute worker original')


def _read(root, request, stage):
    raw = read_bounded_regular_file(_path(root, request, stage), maximum_bytes=65536)
    body = decode_diagnostic_json(raw, maximum=65536)
    if type(body) is not dict or canonical(body) != raw:
        raise ValueError('Canonical absolute worker original required')
    return raw, body


def reserve_absolute_wrist_launch(root, request, *, runtime_original, review_bundle_sha256, now_ns):
    if type(request) is not AbsoluteWristIntent or type(runtime_original) is not bytes:
        raise ValueError('Exact absolute intent and runtime original required')
    request.require_start_time(now_ns)
    runtime = decode_diagnostic_json(runtime_original, maximum=32768)
    if (type(runtime) is not dict or canonical(runtime) != runtime_original
            or hashlib.sha256(runtime_original).hexdigest() != request.to_dict()['references']['runtime_sha256']):
        raise ValueError('Runtime original differs from authenticated reference')
    review = read_bounded_regular_file(_path(root, request, 'reviews'), maximum_bytes=8192)
    if hashlib.sha256(review).hexdigest() != review_bundle_sha256:
        raise ValueError('Review original changed')
    raw = canonical(dict(schema='rocell.absolute_wrist_launch.v1', intent=request.to_dict(),
        runtime=runtime, review_bundle_sha256=review_bundle_sha256, reserved_ns=now_ns,
        process_may_have_started=True, replay_allowed=False, physical_authority=False))
    publish_reservation_bytes(root, _path(root, request, 'launch').name, raw, maximum_bytes=65536)
    if _read(root, request, 'launch')[0] != raw:
        raise ValueError('Launch reservation readback failed')
    return hashlib.sha256(raw).hexdigest()


def _verify_launch(root, request, launch_sha, source_sha, runtime_sha, now_ns):
    request.require_start_time(now_ns)
    raw, body = _read(root, request, 'launch')
    if (set(body) != {'schema', 'intent', 'runtime', 'review_bundle_sha256', 'reserved_ns',
                     'process_may_have_started', 'replay_allowed', 'physical_authority'}
            or body['schema'] != 'rocell.absolute_wrist_launch.v1'
            or hashlib.sha256(raw).hexdigest() != launch_sha
            or canonical(body['intent']) != request.canonical_bytes
            or source_sha != request.to_dict()['references']['source_sha256']
            or runtime_sha != request.to_dict()['references']['runtime_sha256']
            or hashlib.sha256(canonical(body['runtime'])).hexdigest() != runtime_sha
            or type(body['reserved_ns']) is not int
            or not request.to_dict()['issued_ns'] <= body['reserved_ns'] <= now_ns
            or body['process_may_have_started'] is not True or body['replay_allowed'] is not False
            or body['physical_authority'] is not False):
        raise ValueError('Absolute launch context mismatch')
    review = read_bounded_regular_file(_path(root, request, 'reviews'), maximum_bytes=8192)
    if hashlib.sha256(review).hexdigest() != body['review_bundle_sha256']:
        raise ValueError('Original absolute review changed')


class AbsoluteWristWorkerClaim:
    def __init__(self, issuer, request, root, launch_sha, raw):
        if issuer is not _ISSUER:
            raise ValueError('Worker claiming function must issue claim')
        self._request, self._root, self._launch = request, root, launch_sha
        self._raw, self._pid = raw, os.getpid()
        self._used, self._lock = False, Lock()

    @property
    def claim_sha256(self):
        return hashlib.sha256(self._raw).hexdigest()

    def consume(self, request, *, current_source_sha256, current_runtime_sha256, now_ns):
        with self._lock:
            if self._used:
                raise ValueError('Absolute worker claim already consumed')
            self._used = True
            if type(request) is not AbsoluteWristIntent or request != self._request or os.getpid() != self._pid:
                raise ValueError('Absolute worker process/request changed')
            _verify_launch(self._root, request, self._launch, current_source_sha256, current_runtime_sha256, now_ns)
            if _read(self._root, request, 'claimed')[0] != self._raw:
                raise ValueError('Absolute process claim original changed')


def claim_absolute_wrist_worker(root, request, *, launch_sha256, current_source_sha256,
                                current_runtime_sha256, now_ns):
    if type(request) is not AbsoluteWristIntent:
        raise ValueError('Exact absolute intent required')
    _verify_launch(root, request, launch_sha256, current_source_sha256, current_runtime_sha256, now_ns)
    raw = canonical(dict(schema='rocell.absolute_wrist_worker_claim.v1', request_sha256=request.request_sha256,
        launch_sha256=launch_sha256, pid=os.getpid(), claimed_ns=now_ns,
        replay_allowed=False, physical_authority=False))
    publish_reservation_bytes(root, _path(root, request, 'claimed').name, raw, maximum_bytes=8192)
    if _read(root, request, 'claimed')[0] != raw:
        raise ValueError('Absolute process claim readback failed')
    return AbsoluteWristWorkerClaim(_ISSUER, request, safe_root(root), launch_sha256, raw)


def verify_absolute_wrist_worker_receipt(root, request, *, claim_sha256, launch_sha256,
                                        owned_process_id, runtime_sha256, finished_ns):
    raw, body = _read(root, request, 'claimed')
    if (type(owned_process_id) is not int or not 0 < owned_process_id < 2**32
            or type(finished_ns) is not int or not 0 < finished_ns < 2**63
            or set(body) != {'schema', 'request_sha256', 'launch_sha256', 'pid', 'claimed_ns',
                             'replay_allowed', 'physical_authority'}
            or body['schema'] != 'rocell.absolute_wrist_worker_claim.v1'
            or hashlib.sha256(raw).hexdigest() != claim_sha256
            or body['request_sha256'] != request.request_sha256 or body['launch_sha256'] != launch_sha256
            or type(body['pid']) is not int or body['pid'] != owned_process_id
            or type(body['claimed_ns']) is not int or body['claimed_ns'] > finished_ns
            or body['replay_allowed'] is not False or body['physical_authority'] is not False):
        raise ValueError('Absolute owned-process receipt mismatch')
    _verify_launch(root, request, launch_sha256, request.to_dict()['references']['source_sha256'],
                   runtime_sha256, body['claimed_ns'])
    return dict(claim_sha256=claim_sha256, owned_process_id=owned_process_id,
                replay_allowed=False, physical_authority=False)
