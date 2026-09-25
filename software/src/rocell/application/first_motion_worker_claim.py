"""One-use commissioning launch/child records; no process or device access.

These records bind bytes and process ownership; they do not qualify a runtime
or approve movement. The fixed parent registration must independently verify
the executable/package pins before launch. No process or device is opened here.
"""

import base64
import hashlib
import os
from pathlib import Path
from threading import Lock

from .first_motion_contract import FirstMotionRequest
from .physical_onboarding_durability import (
    safe_root, contained_path, publish_reservation_bytes, read_bounded_regular_file,
)
from .wizard_diagnostic_coordinator import decode_diagnostic_json
from .arm_bench_qualification_contract import _canonical

MAX_RECORD_BYTES = 128*1024
_ISSUER = object()


def _path(root, request, stage):
    if type(request) is not FirstMotionRequest or stage not in {'launch','claimed'}:
        raise ValueError('Exact first_motion request and worker stage required')
    return contained_path(safe_root(Path(root)), request.to_dict()['attempt_id']+
                          '-first_motion-worker-'+stage+'.json', label='first_motion worker record')


def _read(path):
    raw = read_bounded_regular_file(path,maximum_bytes=MAX_RECORD_BYTES)
    value = decode_diagnostic_json(raw,maximum=MAX_RECORD_BYTES)
    if type(value) is not dict or _canonical(value) != raw:
        raise ValueError('Canonical original worker record required')
    return raw,value


def reserve_first_motion_launch(root, request, *, runtime_original, review_bundle_sha256, now_ns):
    """Burn the launch ID before the parent creates a process; never resume it.

    runtime_original is the parent-approved canonical registration. This storage
    function does not independently approve its executable, argv or package.
    """
    if type(request) is not FirstMotionRequest:
        raise ValueError('Exact first_motion request required')
    request.require_start_time(now_ns)
    if type(runtime_original) is not bytes or not 0 < len(runtime_original) <= 32768:
        raise ValueError('Bounded original runtime registration required')
    runtime = decode_diagnostic_json(runtime_original,maximum=32768)
    if type(runtime) is not dict or _canonical(runtime) != runtime_original:
        raise ValueError('Canonical runtime registration required')
    import re
    if type(review_bundle_sha256) is not str or re.fullmatch('[0-9a-f]{64}',review_bundle_sha256) is None:
        raise ValueError('Exact review bundle hash required')
    body = {'schema':'rocell.first_motion_worker_launch.v1','request':request.to_dict(),
            'request_sha256':request.request_sha256,
            'runtime_sha256':hashlib.sha256(runtime_original).hexdigest(),
            'runtime_original_base64':base64.b64encode(runtime_original).decode('ascii'),
            'review_bundle_sha256':review_bundle_sha256,'reserved_ns':now_ns,
            'process_may_have_started':True,'replay_allowed':False,'physical_authority':False}
    raw = _canonical(body)
    path = _path(root,request,'launch')
    publish_reservation_bytes(Path(root),path.name,raw,maximum_bytes=MAX_RECORD_BYTES)
    if read_bounded_regular_file(path,maximum_bytes=MAX_RECORD_BYTES) != raw:
        raise ValueError('Launch reservation readback failed')
    return hashlib.sha256(raw).hexdigest()


class FirstMotionWorkerClaim:
    """One process-bound live object. Reading its disk record cannot recreate it."""

    def __init__(self,issuer,request,root,launch_sha,claim_raw):
        if issuer is not _ISSUER: raise ValueError('Worker claiming function required')
        self._request,self._root,self._launch_sha = request,root,launch_sha
        self._claim_raw = claim_raw
        self._pid = os.getpid()
        self._lock,self._used = Lock(),False

    @property
    def claim_sha256(self): return hashlib.sha256(self._claim_raw).hexdigest()

    def consume(self,request,*,current_source_sha256,current_runtime_sha256,now_ns):
        with self._lock:
            if self._used: raise ValueError('Worker claim already consumed')
            self._used = True
            if (os.getpid()!=self._pid or type(request) is not FirstMotionRequest
                    or request.request_sha256 != self._request.request_sha256):
                raise ValueError('Worker process/request association changed')
            _verify_launch(self._root,request,self._launch_sha,current_source_sha256,
                           current_runtime_sha256,now_ns)
            if read_bounded_regular_file(_path(self._root,request,'claimed'),maximum_bytes=MAX_RECORD_BYTES) != self._claim_raw:
                raise ValueError('Worker claim original changed')


def _verify_launch(root,request,launch_sha,source_sha,runtime_sha,now_ns):
    if type(request) is not FirstMotionRequest: raise ValueError('Exact request required')
    request.require_start_time(now_ns)
    raw,body = _read(_path(root,request,'launch'))
    expected = {'schema','request','request_sha256','runtime_sha256','runtime_original_base64',
                'review_bundle_sha256','reserved_ns','process_may_have_started','replay_allowed','physical_authority'}
    if (set(body)!=expected or body['schema']!='rocell.first_motion_worker_launch.v1'
            or hashlib.sha256(raw).hexdigest()!=launch_sha
            or _canonical(body['request'])!=request.canonical_bytes
            or body['request_sha256']!=request.request_sha256
            or source_sha!=request.to_dict()['references']['source_sha256']
            or body['runtime_sha256']!=runtime_sha
            or type(body['reserved_ns']) is not int
            or not request.to_dict()['issued_monotonic_ns'] <= body['reserved_ns'] <= now_ns
            or body['process_may_have_started'] is not True
            or body['replay_allowed'] is not False or body['physical_authority'] is not False):
        raise ValueError('Launch request/source/runtime association mismatch')
    encoded = body['runtime_original_base64']
    if type(encoded) is not str or len(encoded)>43692:
        raise ValueError('Runtime original encoding exceeds budget')
    runtime_raw = base64.b64decode(encoded,validate=True)
    if len(runtime_raw)>32768 or hashlib.sha256(runtime_raw).hexdigest()!=runtime_sha:
        raise ValueError('Runtime original mismatch')
    review_path = contained_path(safe_root(Path(root)),request.to_dict()['attempt_id']+'-first-motion-reviews.json',label='commissioning review original')
    review_raw = read_bounded_regular_file(review_path,maximum_bytes=80*1024)
    if hashlib.sha256(review_raw).hexdigest()!=body['review_bundle_sha256']:
        raise ValueError('Review bundle changed since launch reservation')
    return body


def claim_first_motion_worker(root,request,*,launch_sha256,current_source_sha256,current_runtime_sha256,now_ns):
    _verify_launch(root,request,launch_sha256,current_source_sha256,current_runtime_sha256,now_ns)
    body = {'schema':'rocell.first_motion_worker_claim.v1','request_sha256':request.request_sha256,
            'launch_sha256':launch_sha256,'pid':os.getpid(),'claimed_ns':now_ns,
            'physical_authority':False,'replay_allowed':False}
    raw = _canonical(body)
    path = _path(root,request,'claimed')
    publish_reservation_bytes(Path(root),path.name,raw,maximum_bytes=MAX_RECORD_BYTES)
    if read_bounded_regular_file(path,maximum_bytes=MAX_RECORD_BYTES)!=raw:
        raise ValueError('Claim reservation readback failed')
    return FirstMotionWorkerClaim(_ISSUER,request,safe_root(Path(root)),launch_sha256,raw)


def verify_first_motion_worker_receipt(root, request, *, claim_sha256, launch_sha256,
                                   owned_process_id, runtime_sha256, finished_ns):
    """Associate retained child evidence with the process the parent actually owned.

    The PID must come from the parent supervisor, never from child output. This
    post-exit check uses the original claim time, not a fresh motion authorization.
    It neither consumes nor reconstructs a live claim.
    """
    if type(owned_process_id) is not int or not 0 < owned_process_id < 2**32:
        raise ValueError('Owned supervisor process ID required')
    if type(finished_ns) is not int or not 0 < finished_ns < 2**63:
        raise ValueError('Parent completion time required')
    raw, body = _read(_path(root,request,'claimed'))
    if (set(body)!={'schema','request_sha256','launch_sha256','pid','claimed_ns',
                   'physical_authority','replay_allowed'}
            or body['schema']!='rocell.first_motion_worker_claim.v1'
            or hashlib.sha256(raw).hexdigest()!=claim_sha256
            or body['request_sha256']!=request.request_sha256
            or body['launch_sha256']!=launch_sha256
            or type(body['pid']) is not int or body['pid']!=owned_process_id
            or type(body['claimed_ns']) is not int or body['claimed_ns']>finished_ns
            or body['physical_authority'] is not False or body['replay_allowed'] is not False):
        raise ValueError('Owned process claim association mismatch')
    _verify_launch(root,request,launch_sha256,
                   request.to_dict()['references']['source_sha256'],runtime_sha256,body['claimed_ns'])
    return {'claim_sha256':claim_sha256,'owned_process_id':owned_process_id,
            'physical_authority':False,'replay_allowed':False}
