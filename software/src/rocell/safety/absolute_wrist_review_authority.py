"""Disjoint authentication for one absolute wrist diagnostic, not an IO permit.

No existing native facade accepts this intent. Original references, physical
conditions and fresh owned baseline still require independent boundary checks.
"""
from dataclasses import dataclass
import hashlib
import hmac
import re

from rocell.application.first_motion_contract import canonical
from rocell.application.wizard_diagnostic_coordinator import decode_diagnostic_json
from rocell.motion.absolute_wrist_diagnostic import AbsoluteWristDiagnosticDraft
from .observational_review_authority import validate_observational_context, _review

SCHEMA = 'rocell.absolute_wrist_intent.v1'
BUNDLE = 'rocell.absolute_wrist_review_bundle.v1'
DOMAIN = b'rocell.absolute-wrist-review.v1\x00'


def validate_absolute_intent(body, now_ns):
    fields = {'schema', 'session_id', 'attempt_id', 'usb_identity', 'references',
              'issued_ns', 'deadline_ns', 'draft'}
    if type(body) is not dict or set(body) != fields or body['schema'] != SCHEMA:
        raise ValueError('Exact absolute wrist intent required')
    validate_observational_context(body, now_ns)
    AbsoluteWristDiagnosticDraft(canonical(body['draft']))
    return body


@dataclass(frozen=True, slots=True)
class AbsoluteWristIntent:
    canonical_bytes: bytes

    def __post_init__(self):
        self.to_dict()

    def to_dict(self):
        raw = self.canonical_bytes
        if type(raw) is not bytes:
            raise ValueError('Immutable absolute wrist intent required')
        body = decode_diagnostic_json(raw, maximum=8192)
        if type(body) is not dict or canonical(body) != raw:
            raise ValueError('Canonical absolute wrist intent required')
        return validate_absolute_intent(body, body.get('issued_ns'))

    @property
    def request_sha256(self):
        return hashlib.sha256(self.canonical_bytes).hexdigest()

    def require_start_time(self, now_ns):
        body = validate_absolute_intent(self.to_dict(), now_ns)
        if now_ns + 11_000_000_000 > body['deadline_ns']:
            raise ValueError('Insufficient absolute diagnostic start/cleanup budget')

    def runtime_body(self):
        """Fixed single-command collector budgets, not an expanded intent."""
        from rocell.application.first_motion_contract import fixed_limits
        body = self.to_dict()
        limits = fixed_limits()
        limits['maximum_baseline_bytes'] = 16384
        return dict(body, limits=limits, issued_monotonic_ns=body['issued_ns'],
                    deadline_monotonic_ns=body['deadline_ns'])


class AbsoluteWristReviewAuthority:
    def __init__(self, key):
        if type(key) is not bytes or len(key) != 32:
            raise ValueError('Derived protected 32-byte key required')
        self._key = key

    def seal(self, intent, review, *, now_ns):
        validate_absolute_intent(intent, now_ns)
        _review(review, intent, now_ns)
        body = dict(schema=BUNDLE, intent=intent, review=review)
        body['mac'] = hmac.new(self._key, DOMAIN + canonical(body), hashlib.sha256).hexdigest()
        return canonical(body)

    def verify(self, raw, *, expected_intent, current_usb_identity, current_references, now_ns):
        if type(raw) is not bytes:
            raise ValueError('Original absolute wrist review bytes required')
        body = decode_diagnostic_json(raw, maximum=8192)
        if (type(body) is not dict or set(body) != {'schema', 'intent', 'review', 'mac'}
                or body['schema'] != BUNDLE or canonical(body) != raw):
            raise ValueError('Exact canonical absolute wrist review required')
        mac = body.pop('mac')
        if (type(mac) is not str or not re.fullmatch('[a-f0-9]{64}', mac)
                or not hmac.compare_digest(mac, hmac.new(
                    self._key, DOMAIN + canonical(body), hashlib.sha256).hexdigest())):
            raise ValueError('Absolute wrist review authentication failed')
        intent = validate_absolute_intent(body['intent'], now_ns)
        _review(body['review'], intent, now_ns)
        if (canonical(intent) != canonical(expected_intent)
                or canonical(intent['usb_identity']) != canonical(current_usb_identity)
                or canonical(intent['references']) != canonical(current_references)):
            raise ValueError('Absolute target, start, identity or references changed')
        return dict(intent_sha256=hashlib.sha256(canonical(intent)).hexdigest(),
                    bundle_sha256=hashlib.sha256(raw).hexdigest(), verified_at_ns=now_ns,
                    deadline_ns=intent['deadline_ns'], operator_id=body['review']['operator_id'],
                    physical_truth_verified=False, motion_authorized=False)
