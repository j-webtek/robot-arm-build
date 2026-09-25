"""Authenticate service-issued bench reviews; do not infer physical conditions.

Only a trusted local coordinator may hold the signing key or call ``seal`` after
collecting actual approvals. No wizard route exposes sealing or key input. HMAC
authenticates that coordinator's records, not whether its observations are true.
Production key storage and the operator-review UI are separate integration work.
"""

import base64
from dataclasses import dataclass
import hashlib
import hmac
import json
import re
from pathlib import Path
import time

from rocell.application.endpoint_trial_contract import EndpointTrialRequest
from rocell.application.endpoint_engineering_review import EngineeringDraftReview
from rocell.application.wizard_diagnostic_coordinator import decode_diagnostic_json
from rocell.application.physical_onboarding_durability import contained_path, safe_root, read_bounded_regular_file
from .bench_endpoint import BenchEndpointEvidence, REQUIRED_CHECKS

MAX_BUNDLE_BYTES = 80*1024
_DOMAIN = b'rocell.bench-review-bundle.v1\x00'
OPERATOR_CHECKS = frozenset({'secured_installation','full_arm_and_cable_clearance',
    'gravity_drop_envelope','reachable_power_shutdown','operator_present',
    'exact_target_and_speed_approved','endpoint_only_limitations'})


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True,
                      allow_nan=False).encode('ascii')


def _reviews(request, originals, now_ns):
    if type(request) is not EndpointTrialRequest or type(now_ns) is not int or not 0 < now_ns < 2**63:
        raise ValueError('Exact request and monotonic time required')
    body = request.to_dict()
    if not body['issued_monotonic_ns'] <= now_ns < body['deadline_monotonic_ns']:
        raise ValueError('Review request expired or not yet issued')
    if type(originals) is not dict or set(originals) != REQUIRED_CHECKS:
        raise ValueError('All bench review originals required')
    expected = {'schema','scope','check','decision','actor_id','evidence_kind',
                'request_sha256','recorded_ns','expires_ns','detail'}
    hashes, expiry = [], body['deadline_monotonic_ns']
    for name in sorted(REQUIRED_CHECKS):
        raw = originals[name]
        if type(raw) is not bytes or not 0 < len(raw) <= 4096:
            raise ValueError('Bounded nonempty review originals required')
        review = decode_diagnostic_json(raw, maximum=4096)
        bridged = type(review) is dict and review.get('schema') == 'rocell.bench_endpoint_review.v2'
        if type(review) is not dict or set(review) != (expected|{'draft_review_b64'} if bridged else expected) or _canonical(review) != raw:
            raise ValueError('Review fields or canonical original mismatch')
        kind = 'ENGINEERING_DRAFT_REVIEW_BINDING' if bridged else (
            'OPERATOR_ATTESTATION' if name in OPERATOR_CHECKS else 'ENGINEERING_REVIEW')
        if (review['schema'] != ('rocell.bench_endpoint_review.v2' if bridged else 'rocell.bench_endpoint_review.v1')
                or review['scope'] != 'ONE_NONCONTACT_BENCH_ENDPOINT'
                or review['check'] != name or review['decision'] != 'APPROVED'
                or review['request_sha256'] != request.request_sha256
                or review['evidence_kind'] != kind):
            raise ValueError('Review scope, decision or exact request mismatch')
        if (type(review['actor_id']) is not str
                or re.fullmatch(r'[A-Za-z0-9_.-]{1,64}', review['actor_id']) is None
                or type(review['detail']) is not str or not 1 <= len(review['detail'].strip()) <= 1024):
            raise ValueError('Identified reviewer and bounded rationale required')
        recorded, expires = review['recorded_ns'], review['expires_ns']
        if (type(recorded) is not int or type(expires) is not int
                or not body['issued_monotonic_ns'] <= recorded <= now_ns < expires
                or expires > body['deadline_monotonic_ns']):
            raise ValueError('Review is stale or extends the request deadline')
        if bridged:
            if name in OPERATOR_CHECKS or type(review['draft_review_b64']) is not str:
                raise ValueError('Draft reviews cannot replace current operator checks')
            original = EngineeringDraftReview(base64.b64decode(review['draft_review_b64'],validate=True))
            decision = original.validate_for_request(request, now_ns)
            if (decision['check'] != name or decision['actor_id'] != review['actor_id']
                    or decision['recorded_ns'] > recorded or expires > decision['expires_ns']):
                raise ValueError('Engineering original association or expiry changed')
        expiry = min(expiry, expires)
        hashes.append((name, hashlib.sha256(raw).hexdigest()))
    return tuple(hashes), expiry


class BenchReviewAuthority:
    """Process-local authority supplied by a protected coordinator key.

    This class grants no port access and does not issue a motion permit. Never
    construct it from an uploaded key or allow browser callers to submit reviews
    to ``seal``. Restart/key lifecycle and protected storage belong to the host.
    """

    def __init__(self, key):
        if type(key) is not bytes or not 32 <= len(key) <= 64:
            raise ValueError('Protected service key of 32–64 bytes required')
        self._key = key

    def for_first_motion(self):
        """Derive a disjoint authority without exporting the protected host key.

        This is a trusted-host API, not a browser signing or approval endpoint.
        Neither authority can authenticate the other's bundle format.
        """
        from .first_motion_review_authority import FirstMotionReviewAuthority
        derived=hmac.new(self._key,b'rocell.first-motion-key-derivation.v1\x00',hashlib.sha256).digest()
        return FirstMotionReviewAuthority(derived)

    def for_observational_motion(self):
        """Disjoint host-only authority for the measurement-free test policy."""
        from .observational_review_authority import ObservationalReviewAuthority
        derived = hmac.new(self._key, b'rocell.observational-key-derivation.v1\x00', hashlib.sha256).digest()
        return ObservationalReviewAuthority(derived)

    def for_positional_campaign(self):
        """Separate campaign review key domain; does not grant serial authority."""
        from .positional_campaign_authority import PositionalCampaignReviewAuthority
        derived = hmac.new(self._key,b'rocell.positional-campaign-key-derivation.v1\x00',hashlib.sha256).digest()
        return PositionalCampaignReviewAuthority(derived)

    def for_absolute_wrist_diagnostic(self):
        """Separate absolute-target review; does not create keys or native permits."""
        from .absolute_wrist_review_authority import AbsoluteWristReviewAuthority
        derived = hmac.new(self._key, b'rocell.absolute-wrist-key-derivation.v1\x00', hashlib.sha256).digest()
        return AbsoluteWristReviewAuthority(derived)

    def for_wrist_correction_review(self):
        """Disjoint correction review domain; no native permit or key creation."""
        from .wrist_correction_review_authority import WristCorrectionReviewAuthority
        derived = hmac.new(self._key, b'rocell.wrist-correction-key-derivation.v1\x00', hashlib.sha256).digest()
        return WristCorrectionReviewAuthority(derived)

    def seal(self, request, originals, *, now_ns):
        """Trusted coordinator only, after actual request-specific review.

        Originals must already include all final decisions. This method never
        turns a missing/unknown/denied check into approval or refreshes its time.
        """
        _reviews(request, originals, now_ns)
        body = {'schema':'rocell.bench_review_bundle.v1',
                'request_sha256':request.request_sha256,
                'originals':{name:base64.b64encode(raw).decode('ascii') for name,raw in originals.items()}}
        body['mac'] = hmac.new(self._key, _DOMAIN+_canonical(body), hashlib.sha256).hexdigest()
        raw = _canonical(body)
        if len(raw)>MAX_BUNDLE_BYTES:
            raise ValueError('Review bundle exceeds storage budget')
        return raw

    def verify(self, request, raw, *, connection_id, current_references, now_ns):
        """Authenticate originals and bind them to service-verified current state.

        current_references and connection_id must come from the owned worker's
        current identity/source/configuration validation, never browser input.
        """
        if type(request) is not EndpointTrialRequest or type(raw) is not bytes:
            raise ValueError('Exact request and original bundle bytes required')
        body = decode_diagnostic_json(raw, maximum=MAX_BUNDLE_BYTES)
        if (type(body) is not dict or set(body) != {'schema','request_sha256','originals','mac'}
                or _canonical(body) != raw or body['schema'] != 'rocell.bench_review_bundle.v1'
                or body['request_sha256'] != request.request_sha256):
            raise ValueError('Review bundle context mismatch')
        mac = body.pop('mac')
        if (type(mac) is not str or re.fullmatch('[0-9a-f]{64}', mac) is None
                or not hmac.compare_digest(mac, hmac.new(self._key, _DOMAIN+_canonical(body), hashlib.sha256).hexdigest())):
            raise ValueError('Review bundle authentication failed')
        encoded = body['originals']
        if (type(encoded) is not dict or set(encoded) != REQUIRED_CHECKS
                or any(type(item) is not str or len(item)>5464 for item in encoded.values())):
            raise ValueError('Bounded original review encodings required')
        originals = {name:base64.b64decode(value, validate=True) for name,value in encoded.items()}
        checks, expiry = _reviews(request, originals, now_ns)
        expected_refs = tuple(sorted(request.to_dict()['references'].items()))
        if (type(connection_id) is not str or not 1 <= len(connection_id) <= 80
                or current_references != expected_refs):
            raise ValueError('Owned connection/current review context mismatch')
        return BenchEndpointEvidence(request.request_sha256, connection_id, expected_refs,
                                     checks, now_ns, expiry)


@dataclass(frozen=True, slots=True)
class BenchReviewCurrentContext:
    """Owned worker validation result; not an operator-supplied JSON assertion."""

    connection_id: str
    usb_identity: tuple[int, int, str]
    references: tuple[tuple[str, str], ...]
    observed_ns: int
    port_name: str | None = None


class AuthenticatedBenchReviewReader:
    """Reopen a fixed attempt record and verify it at every permit check.

    Host setup supplies a protected authority, canonical review root and live
    context reader. There is no fallback to unsigned data or cached approval.
    """

    def __init__(self, request, *, authority, review_root, connection_id,
                 context_reader, clock_ns=time.monotonic_ns):
        if (type(request) is not EndpointTrialRequest or type(authority) is not BenchReviewAuthority
                or type(connection_id) is not str or not 1 <= len(connection_id) <= 80
                or not callable(context_reader) or not callable(clock_ns)):
            raise ValueError('Trusted review authority and owned context dependencies required')
        self._request, self._authority = request, authority
        self._root = safe_root(Path(review_root))
        self._connection_id, self._context_reader, self._clock = connection_id, context_reader, clock_ns

    def __call__(self):
        return self._read(None)

    def presence_expiry(self):
        """Authenticate original approval expiry only; no device-state claim.

        Always reread and authenticate the bundle. This does not return native
        admission evidence or replace consume/dispatch current-context checks.
        """
        evidence = self._authority.verify(self._request,self._original(),
            connection_id=self._connection_id,
            current_references=tuple(sorted(self._request.to_dict()['references'].items())),
            now_ns=self._clock())
        return evidence.expires_at_ns

    def verify_endpoint(self, port_name):
        if type(port_name) is not str or re.fullmatch(r'COM[1-9][0-9]{0,3}', port_name) is None:
            raise ValueError('Exact Windows COM endpoint required')
        return self._read(port_name)

    def _original(self):
        body = self._request.to_dict()
        return read_bounded_regular_file(contained_path(self._root,
            body['attempt_id']+'-bench-reviews.json', label='bench review originals'),
            maximum_bytes=MAX_BUNDLE_BYTES)

    def _read(self, port_name):
        body = self._request.to_dict()
        raw = self._original()
        context = self._context_reader()
        now = self._clock()
        identity = body['usb_identity']
        if (type(now) is not int or not 0 < now < 2**63
                or type(context) is not BenchReviewCurrentContext
                or context.connection_id != self._connection_id
                or (port_name is not None and context.port_name != port_name)
                or context.usb_identity != (identity['vid'],identity['pid'],identity['serial_number'])
                or type(context.observed_ns) is not int
                or not body['issued_monotonic_ns'] <= context.observed_ns <= now
                or now-context.observed_ns > 100_000_000):
            raise ValueError('Current owned identity is unavailable, changed or stale')
        return self._authority.verify(self._request, raw, connection_id=self._connection_id,
                                      current_references=context.references, now_ns=now)
