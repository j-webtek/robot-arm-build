"""Durable intake of actual host review decisions for one exact live request.

This is a trusted parent dependency, not a browser signing endpoint. Callers
must obtain the named actor's actual decision; this collector performs no
physical checks and cannot infer approval from a setup checkbox or old receipt.
It never extends the request lifetime, signs a bundle, or opens a device.
"""

from pathlib import Path
import re
import time

from .endpoint_trial_contract import EndpointTrialRequest
from .physical_onboarding_durability import (
    safe_root, contained_path, publish_reservation_bytes, read_bounded_regular_file,
)
from .wizard_diagnostic_coordinator import decode_diagnostic_json
from rocell.safety.bench_endpoint import REQUIRED_CHECKS
from rocell.safety.bench_review_authority import OPERATOR_CHECKS, _canonical


class EndpointReviewIntake:
    """Immutable per-check originals with separate operator/engineering readers.

    A denial or unknown decision is retained and cannot be overwritten with an
    approval. A new review needs a new request/attempt, not an automatic retry.
    Trusted callers supply role-specific actors; actor strings alone are not
    authentication. The existing issuance authority remains responsible for
    validating the complete set and current hardware/reference context.
    """

    def __init__(self, request, *, root, clock_ns=time.monotonic_ns):
        if type(request) is not EndpointTrialRequest or not callable(clock_ns):
            raise ValueError('Exact request and host clock required')
        self._request = request
        self._root = safe_root(Path(root))
        self._clock = clock_ns

    def _filename(self, check):
        if type(check) is not str or check not in REQUIRED_CHECKS:
            raise ValueError('Known endpoint check required')
        return self._request.to_dict()['attempt_id']+'-'+check+'-review-original.json'

    def record(self, *, check, actor_id, decision, detail, expires_ns):
        """Record one explicit decision now; never accept a caller's timestamp."""
        filename = self._filename(check)
        now = self._clock()
        body = self._request.to_dict()
        self._request.require_start_time(now)
        if (type(actor_id) is not str
                or re.fullmatch(r'[A-Za-z0-9_.-]{1,64}', actor_id) is None
                or type(decision) is not str
                or decision not in {'APPROVED', 'DENIED', 'UNKNOWN'}
                or type(detail) is not str or not 1 <= len(detail.strip()) <= 1024
                or type(expires_ns) is not int
                or not now < expires_ns <= body['deadline_monotonic_ns']):
            raise ValueError('Explicit identified, bounded review decision required')
        raw = _canonical({
            'schema': 'rocell.bench_endpoint_review.v1',
            'scope': 'ONE_NONCONTACT_BENCH_ENDPOINT',
            'check': check, 'actor_id': actor_id, 'decision': decision,
            'detail': detail, 'request_sha256': self._request.request_sha256,
            'recorded_ns': now, 'expires_ns': expires_ns,
            'evidence_kind': 'OPERATOR_ATTESTATION' if check in OPERATOR_CHECKS
                else 'ENGINEERING_REVIEW',
        })
        publish_reservation_bytes(self._root, filename, raw, maximum_bytes=4096)
        return raw

    def _read(self, request, checks):
        if (type(request) is not EndpointTrialRequest
                or request.canonical_bytes != self._request.canonical_bytes):
            raise ValueError('Review intake belongs to another exact request')
        now = self._clock()
        request.require_start_time(now)
        result = {}
        for check in sorted(checks):
            path = contained_path(self._root, self._filename(check), label='review original')
            raw = read_bounded_regular_file(path, maximum_bytes=4096)
            value = decode_diagnostic_json(raw, maximum=4096)
            # The sealing authority subsequently validates every schema field.
            # Fail here on refusal/expiry without rewriting the retained record.
            if (type(value) is not dict or _canonical(value) != raw
                    or value.get('check') != check
                    or value.get('request_sha256') != request.request_sha256
                    or value.get('decision') != 'APPROVED'
                    or type(value.get('recorded_ns')) is not int
                    or type(value.get('expires_ns')) is not int
                    or not request.to_dict()['issued_monotonic_ns']
                        <= value['recorded_ns'] <= now < value['expires_ns']
                        <= request.to_dict()['deadline_monotonic_ns']):
                raise ValueError('Review missing approval, changed or expired')
            result[check] = raw
        request.require_start_time(self._clock())
        return result

    def operator_reader(self, request):
        return self._read(request, OPERATOR_CHECKS)

    def engineering_reader(self, request):
        return self._read(request, REQUIRED_CHECKS-OPERATOR_CHECKS)
