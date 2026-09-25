"""Separate one-target bench admission; never releases a commissioned cell.

The evidence reader is a trusted service dependency, not JSON from the wizard.
It must authenticate retained originals and current physical attestations. This
module deliberately cannot open a device. Native claim/worker integration must
still enforce exclusive ownership and revalidate originals before dispatch.
"""

from dataclasses import dataclass
from threading import Lock
import re
import time

from rocell.application.endpoint_trial_contract import EndpointTrialRequest
from rocell.application.endpoint_attempt_reservation import EndpointAttemptReservation


REQUIRED_CHECKS = frozenset({
    'received_unit_and_usb_association', 'installed_firmware_compatibility',
    'secured_installation', 'full_arm_and_cable_clearance',
    'gravity_drop_envelope', 'reachable_power_shutdown',
    'operator_present', 'exact_target_and_speed_approved',
    'controller_frame_and_baseline_qualified', 'endpoint_only_limitations',
    'noncontact_route_review', 'owned_connection_and_cleanup_ready',
})
_ISSUER = object()


@dataclass(frozen=True, slots=True)
class BenchEndpointEvidence:
    """Authenticated service result, not proof merely because it has this type.

    Each check pairs its name with a retained review SHA-256. The service must
    verify the original's meaning, approval and request association. Hash-shaped
    values alone are not approvals. No camera/tag-map release is required here.
    """

    request_sha256: str
    connection_id: str
    references: tuple[tuple[str, str], ...]
    checks: tuple[tuple[str, str], ...]
    verified_at_ns: int
    expires_at_ns: int


def _validate(request, evidence, connection_id, now):
    if type(now) is not int or not 0 < now < 2**63:
        raise ValueError('Invalid bench clock')
    body = request.to_dict()
    if type(evidence) is not BenchEndpointEvidence:
        raise ValueError('Authenticated bench evidence required')
    if (evidence.request_sha256 != request.request_sha256
            or evidence.connection_id != connection_id
            or evidence.references != tuple(sorted(body['references'].items()))):
        raise ValueError('Bench evidence association changed')
    checks = evidence.checks
    if (type(checks) is not tuple or len(checks) != len(REQUIRED_CHECKS)
            or any(type(row) is not tuple or len(row) != 2 for row in checks)):
        raise ValueError('Missing bench reviews')
    if (any(type(name) is not str or type(digest) is not str
            or re.fullmatch('[0-9a-f]{64}', digest) is None
            or digest == '0'*64 for name, digest in checks)
            or {name for name, _ in checks} != REQUIRED_CHECKS):
        raise ValueError('Invalid bench reviews')
    if (type(evidence.verified_at_ns) is not int
            or type(evidence.expires_at_ns) is not int
            or not body['issued_monotonic_ns'] <= evidence.verified_at_ns <= now
            or now-evidence.verified_at_ns > 100_000_000
            or not now < evidence.expires_at_ns <= body['deadline_monotonic_ns']):
        raise ValueError('Bench evidence is stale or unbounded')


class BenchEndpointPermit:
    """Opaque one-attempt capability: request AND owned connection, not campaign.

    Consumption is irreversible even when revalidation fails. This is an
    in-process guard, not protection from malicious trusted Python code.
    """

    def __init__(self, issuer, request, connection_id, evidence_reader, clock, checks, reservation):
        if issuer is not _ISSUER:
            raise ValueError('Bench admission must issue the permit')
        self._request = request
        self._connection_id = connection_id
        self._reader = evidence_reader
        self._clock = clock
        self._checks = tuple(sorted(checks))
        self._reservation = reservation
        self._lock = Lock()
        self._used = False
        self._native_open_claimed = False
        self._dispatch_ready = False
        self._native_dispatch_claimed = False
        self._baseline_deadline_ns = None

    def consume(self, request, connection_id, *, baseline_acquired_ns=None):
        with self._lock:
            if self._used:
                return False
            self._used = True
            try:
                if baseline_acquired_ns is not None:
                    if type(baseline_acquired_ns) is not int or not 0 < baseline_acquired_ns <= self._clock():
                        return False
                    self._baseline_deadline_ns = baseline_acquired_ns+100_000_000
                if (type(request) is not EndpointTrialRequest
                        or request.request_sha256 != self._request.request_sha256
                        or connection_id != self._connection_id):
                    return False
                evidence = self._reader()
                if not self._reservation.intact():
                    return False
                now = self._clock()
                _validate(request, evidence, connection_id, now)
                if tuple(sorted(evidence.checks)) != self._checks:
                    return False
                allowed = now+8_000_000_000 <= request.to_dict()['deadline_monotonic_ns']
                self._dispatch_ready = allowed
                return allowed
            except Exception:
                return False

    def revoke(self):
        with self._lock:
            self._used = True
            self._dispatch_ready = False

    def _native_review(self, request, connection_id, port_name):
        # Only the authenticated file reader is admissible at the native edge;
        # incapable test readers remain useful for rehearsal but cannot open it.
        from .bench_review_authority import AuthenticatedBenchReviewReader
        if (type(self._reader) is not AuthenticatedBenchReviewReader
                or type(request) is not EndpointTrialRequest
                or request.request_sha256 != self._request.request_sha256
                or connection_id != self._connection_id or not self._reservation.intact()):
            raise ValueError('Authenticated native bench context required')
        evidence = self._reader.verify_endpoint(port_name)
        now = self._clock()
        _validate(request, evidence, connection_id, now)
        if tuple(sorted(evidence.checks)) != self._checks:
            raise ValueError('Native bench review changed')
        return now

    def claim_native_open(self, request, connection_id, port_name):
        with self._lock:
            if self._used or self._native_open_claimed:
                raise ValueError('Native bench open already claimed or revoked')
            self._native_open_claimed = True
            try:
                request.require_start_time(self._native_review(request, connection_id, port_name))
            except Exception:
                self._used = True
                raise

    def validate_native_open(self, request, connection_id, port_name):
        with self._lock:
            if self._used or not self._native_open_claimed:
                raise ValueError('Native open permission expired or revoked')
            request.require_start_time(self._native_review(request, connection_id, port_name))

    def claim_native_dispatch(self, request, connection_id, port_name):
        with self._lock:
            if not self._native_open_claimed or not self._dispatch_ready or self._native_dispatch_claimed:
                raise ValueError('Consumed endpoint permission required for native dispatch')
            self._native_dispatch_claimed = True
            self._dispatch_ready = False
            now = self._native_review(request, connection_id, port_name)
            if self._baseline_deadline_ns is None or now>self._baseline_deadline_ns:
                raise ValueError('Native dispatch baseline missing or expired')
            if now+8_000_000_000 > request.to_dict()['deadline_monotonic_ns']:
                raise ValueError('Native dispatch budget expired')


def authorize_bench_endpoint(request, *, connection_id, evidence_reader, attempt_root,
                             clock=time.monotonic_ns):
    """Issue only after a trusted service authenticates all bench-specific reviews.

    Never expose evidence_reader/clock/attempt_root as browser inputs. The root
    must be stable across application restarts and qualified for physical use.
    Reserving the ID is irreversible, including if issuance later fails.
    """
    if type(request) is not EndpointTrialRequest:
        raise ValueError('Exact endpoint request required')
    if (type(connection_id) is not str or not 1 <= len(connection_id) <= 80
            or not callable(evidence_reader) or not callable(clock)):
        raise ValueError('Owned service dependencies required')
    evidence = evidence_reader()
    now = clock()
    request.require_start_time(now)
    _validate(request, evidence, connection_id, now)
    reservation = EndpointAttemptReservation(attempt_root, request, connection_id, evidence)
    # Disk publication can take time. Do not issue from stale evidence or extend
    # the request deadline to compensate for that delay.
    refreshed = evidence_reader()
    now = clock()
    request.require_start_time(now)
    _validate(request, refreshed, connection_id, now)
    if tuple(sorted(refreshed.checks)) != tuple(sorted(evidence.checks)):
        raise ValueError('Bench reviews changed during reservation')
    return BenchEndpointPermit(_ISSUER, request, connection_id, evidence_reader, clock,
                               evidence.checks, reservation)
