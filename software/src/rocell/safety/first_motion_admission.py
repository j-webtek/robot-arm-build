"""Durable one-use commissioning admission; no device or transport operations.

In-process capabilities are not isolation from malicious trusted Python code.
No normal endpoint permit, arbitrary callback or browser receipt can substitute
for the separate authenticated commissioning reader at this boundary.
"""
import hashlib
import re
from pathlib import Path
from threading import Lock
import time

from rocell.application.first_motion_contract import FirstMotionRequest, canonical
from rocell.application.physical_onboarding_durability import (
    safe_root, contained_path, publish_reservation_bytes, read_bounded_regular_file,
)
from .first_motion_review_authority import (
    AuthenticatedFirstMotionReviewReader, FirstMotionReviewEvidence, REQUIRED_CHECKS,
)

_ISSUER=object()


def _validate(request,evidence,now):
    body=request.to_dict()
    if (type(now) is not int or not 0<now<2**63
            or type(evidence) is not FirstMotionReviewEvidence
            or evidence.request_sha256!=request.request_sha256
            or evidence.connection_id!=body['attempt_id']
            or evidence.references!=tuple(sorted(body['references'].items()))
            or type(evidence.checks) is not tuple or len(evidence.checks)!=len(REQUIRED_CHECKS)
            or {name for name,_ in evidence.checks}!=REQUIRED_CHECKS
            or type(evidence.verified_at_ns) is not int or type(evidence.expires_at_ns) is not int
            or not body['issued_monotonic_ns']<=evidence.verified_at_ns<=now
            or now-evidence.verified_at_ns>100_000_000
            or not now<evidence.expires_at_ns<=body['deadline_monotonic_ns']):
        raise ValueError('Current authenticated commissioning evidence required')


class _Reservation:
    def __init__(self,root,request,evidence):
        root=safe_root(Path(root))
        name=request.to_dict()['attempt_id']+'-first-motion-reserved.json'
        self._path=contained_path(root,name,label='one-use commissioning reservation')
        raw=canonical({'schema':'rocell.first_motion_reservation.v1',
            'request':request.to_dict(),'request_sha256':request.request_sha256,
            'review_hashes':dict(evidence.checks),'verified_at_ns':evidence.verified_at_ns,
            'expires_at_ns':evidence.expires_at_ns,'replay_allowed':False,
            'physical_movement_verified':False})
        # Exclusive publication burns even an interrupted/partial reservation.
        publish_reservation_bytes(root,name,raw,maximum_bytes=32768)
        self._sha=hashlib.sha256(raw).hexdigest()
        if not self.intact(): raise ValueError('Commissioning reservation readback failed')

    def intact(self):
        try:
            return hashlib.sha256(read_bounded_regular_file(self._path,maximum_bytes=32768)).hexdigest()==self._sha
        except Exception:
            return False


class FirstMotionPermit:
    """One exact request/open/write state machine, revoked irreversibly on failure."""
    def __init__(self,issuer,request,reader,reservation,checks,clock,initial_now):
        if issuer is not _ISSUER: raise ValueError('Commissioning admission must issue this permit')
        self._request,self._reader,self._reservation=request,reader,reservation
        self._checks=checks
        self._clock=clock
        self._lock=Lock()
        self._last_ns=initial_now
        self._revoked=self._opened=self._consumed=self._dispatched=False
        self._ready=False
        self._baseline_deadline=None
        self._port=None

    def _review(self,request,connection_id,port_name=None):
        if (type(request) is not FirstMotionRequest or request.request_sha256!=self._request.request_sha256
                or connection_id!=self._request.to_dict()['attempt_id']
                or type(self._reader) is not AuthenticatedFirstMotionReviewReader
                or (port_name is not None and self._port is not None and port_name!=self._port)
                or not self._reservation.intact()):
            raise ValueError('Exact owned commissioning context required')
        # Consumption has no caller-supplied port: still recheck the endpoint
        # pinned by the one allowed open, not merely the USB identity.
        evidence=self._reader.verify_endpoint(self._port if port_name is None else port_name)
        now=self._clock()
        if type(now) is not int or now<self._last_ns:
            raise ValueError('Invalid/backwards commissioning clock')
        self._last_ns=now
        _validate(request,evidence,now)
        if evidence.checks!=self._checks: raise ValueError('Commissioning approvals changed')
        return now

    def revoke(self):
        with self._lock:
            self._revoked=True
            self._ready=False

    def claim_native_open(self,request,connection_id,port_name):
        with self._lock:
            if self._revoked or self._opened: raise ValueError('Commissioning open already claimed or revoked')
            self._opened=True
            try:
                if (type(port_name) is not str or not re.fullmatch(r'COM[1-9][0-9]{0,3}',port_name)
                        or int(port_name[3:])>4096):
                    raise ValueError('Exact owned COM endpoint required')
                self._port=port_name
                request.require_start_time(self._review(request,connection_id,port_name))
            except Exception:
                self._revoked=True
                raise

    def validate_native_open(self,request,connection_id,port_name):
        with self._lock:
            if self._revoked or not self._opened or self._consumed:
                raise ValueError('Commissioning open permission unavailable')
            try:
                if port_name!=self._port: raise ValueError('Pinned commissioning port required')
                request.require_start_time(self._review(request,connection_id,port_name))
            except Exception:
                self._revoked=True
                raise

    def consume_for_write(self,request,connection_id,*,baseline_acquired_ns):
        with self._lock:
            if self._revoked or self._consumed: return False
            self._consumed=True
            if not self._opened:
                self._revoked=True
                return False
            try:
                now=self._review(request,connection_id)
                if (type(baseline_acquired_ns) is not int
                        or not request.to_dict()['issued_monotonic_ns']<=baseline_acquired_ns<=now
                        or now-baseline_acquired_ns>100_000_000
                        or now+8_000_000_000>request.to_dict()['deadline_monotonic_ns']):
                    raise ValueError('Baseline acquisition or remaining budget invalid')
                # Host capture recency only; device sample freshness stays unknown.
                self._baseline_deadline=baseline_acquired_ns+100_000_000
                self._ready=True
                return True
            except Exception:
                self._revoked=True
                return False

    def claim_native_dispatch(self,request,connection_id,port_name):
        with self._lock:
            if self._revoked or not self._opened or not self._ready or self._dispatched:
                raise ValueError('Consumed one-use commissioning write permission required')
            self._dispatched=True
            self._ready=False
            try:
                if port_name!=self._port: raise ValueError('Pinned commissioning port required')
                now=self._review(request,connection_id,port_name)
                if now>self._baseline_deadline or now+8_000_000_000>request.to_dict()['deadline_monotonic_ns']:
                    raise ValueError('Commissioning dispatch observation/budget expired')
            except Exception:
                self._revoked=True
                raise


def authorize_first_motion(request,*,evidence_reader,attempt_root,clock=time.monotonic_ns):
    """Trusted host only; the root must be stable across restarts, never UI input."""
    if (type(request) is not FirstMotionRequest
            or type(evidence_reader) is not AuthenticatedFirstMotionReviewReader
            or not callable(clock)):
        raise ValueError('Separate typed commissioning admission dependencies required')
    initial=evidence_reader()
    before=clock()
    request.require_start_time(before)
    _validate(request,initial,before)
    reservation=_Reservation(attempt_root,request,initial)
    refreshed=evidence_reader()
    now=clock()
    request.require_start_time(now)
    _validate(request,refreshed,now)
    if now<before or refreshed.checks!=initial.checks:
        raise ValueError('Commissioning evidence changed during reservation')
    return FirstMotionPermit(_ISSUER,request,evidence_reader,reservation,initial.checks,clock,now)
