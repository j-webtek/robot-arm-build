"""Authenticate an observational test policy without inventing measurements.

Trusted host-only sealing. Authentication proves record association, not physical
truth, device freshness, clearance, or permission to open a serial connection.
"""
import hashlib
import hmac
import re
from dataclasses import dataclass

from rocell.application.first_motion_contract import canonical
from rocell.application.wizard_diagnostic_coordinator import decode_diagnostic_json
from rocell.motion.observational_wrist_plan import policy_degrees

CHECKS = frozenset(('secured_and_clear', 'operator_present_and_shutdown_reachable',
                    'starting_pose_visually_consistent', 'bounded_policy_accepted'))
REFERENCES = frozenset(('source_sha256', 'runtime_sha256', 'protocol_review_sha256',
                        'native_controller_review_sha256'))
_DOMAIN = b'rocell.observational-review.v1\x00'


def validate_intent(intent, now_ns):
    fields = {'schema', 'session_id', 'attempt_id', 'usb_identity', 'references',
              'issued_ns', 'deadline_ns', 'direction', 'policy'}
    if type(intent) is not dict or set(intent) != fields or intent['schema'] != 'rocell.observational_intent.v1':
        raise ValueError('Exact observational intent required')
    validate_observational_context(intent, now_ns)
    policy_degrees(intent['policy'])
    if (type(intent['direction']) is not int or intent['direction'] not in (-1, 1)):
        raise ValueError('Only the bounded observational wrist policy is supported')
    return intent


def validate_observational_context(intent, now_ns):
    """Shared identity/reference/time checks AFTER an exact schema validation.

    This helper validates no motion policy and issues no authority. Callers must
    independently validate their distinct relative or absolute contract.
    """
    for name, prefix in (('session_id', 'wizard-'), ('attempt_id', 'operation-')):
        if type(intent[name]) is not str or not re.fullmatch(prefix+'[a-f0-9]{32}', intent[name]):
            raise ValueError('Host session and attempt IDs required')
    identity = intent['usb_identity']
    if (type(identity) is not dict or set(identity) != {'vid', 'pid', 'serial_number'}
            or type(identity['vid']) is not int or identity['vid'] != 0x10c4
            or type(identity['pid']) is not int or identity['pid'] != 0xea60
            or type(identity['serial_number']) is not str
            or not re.fullmatch('[A-F0-9]{32}', identity['serial_number'])):
        raise ValueError('Exact USB identity required')
    refs = intent['references']
    if (type(refs) is not dict or set(refs) != REFERENCES
            or any(type(v) is not str or not re.fullmatch('[a-f0-9]{64}', v) or v == '0'*64
                   for v in refs.values())):
        raise ValueError('Source, runtime and protocol references required')
    issued, deadline = intent['issued_ns'], intent['deadline_ns']
    if (any(type(v) is not int for v in (issued, deadline, now_ns))
            or not 0 < issued <= now_ns < deadline < 2**63
            or not 11_000_000_000 <= deadline-issued <= 30_000_000_000):
        raise ValueError('Current bounded intent lifetime required')


def _review(review, intent, now_ns):
    if (type(review) is not dict or set(review) != {'operator_id', 'recorded_ns', 'checks'}
            or type(review['operator_id']) is not str
            or not re.fullmatch('[A-Za-z0-9][A-Za-z0-9_.-]{0,63}', review['operator_id'])
            or type(review['recorded_ns']) is not int
            or not intent['issued_ns'] <= review['recorded_ns'] <= now_ns
            or type(review['checks']) is not dict or set(review['checks']) != CHECKS
            or any(v is not True for v in review['checks'].values())):
        raise ValueError('Explicit current operator confirmation required; no default approvals')


@dataclass(frozen=True, slots=True)
class ObservationalIntent:
    """Immutable observational policy, distinct from measured/Cartesian requests."""
    canonical_bytes: bytes

    def __post_init__(self):
        self.to_dict()

    def to_dict(self):
        if type(self.canonical_bytes) is not bytes:
            raise ValueError('Immutable observational intent bytes required')
        value = decode_diagnostic_json(self.canonical_bytes, maximum=8192)
        if type(value) is not dict or canonical(value) != self.canonical_bytes:
            raise ValueError('Canonical observational intent required')
        return validate_intent(value, value.get('issued_ns'))

    @property
    def request_sha256(self):
        return hashlib.sha256(self.canonical_bytes).hexdigest()

    def require_start_time(self, now_ns):
        body = validate_intent(self.to_dict(), now_ns)
        if now_ns + 11_000_000_000 > body['deadline_ns']:
            raise ValueError('Insufficient observational start/cleanup budget')

    def runtime_body(self):
        """Fixed resource limits for internal collectors; not a changed intent."""
        from rocell.application.first_motion_contract import fixed_limits
        body = self.to_dict()
        return dict(body, limits=fixed_limits(), issued_monotonic_ns=body['issued_ns'],
                    deadline_monotonic_ns=body['deadline_ns'])


class ObservationalReviewAuthority:
    def __init__(self, key):
        if type(key) is not bytes or len(key) != 32:
            raise ValueError('Derived protected 32-byte key required')
        self._key = key

    def seal(self, intent, review, *, now_ns):
        validate_intent(intent, now_ns)
        _review(review, intent, now_ns)
        body = dict(schema='rocell.observational_review_bundle.v1', intent=intent, review=review)
        body['mac'] = hmac.new(self._key, _DOMAIN+canonical(body), hashlib.sha256).hexdigest()
        return canonical(body)

    def verify(self, raw, *, expected_intent, current_usb_identity, current_references, now_ns):
        body = decode_diagnostic_json(raw, maximum=8192)
        if (type(raw) is not bytes or type(body) is not dict
                or set(body) != {'schema', 'intent', 'review', 'mac'}
                or body['schema'] != 'rocell.observational_review_bundle.v1'
                or canonical(body) != raw):
            raise ValueError('Exact canonical observational review bundle required')
        mac = body.pop('mac')
        if (type(mac) is not str or not re.fullmatch('[a-f0-9]{64}', mac)
                or not hmac.compare_digest(mac, hmac.new(self._key, _DOMAIN+canonical(body), hashlib.sha256).hexdigest())):
            raise ValueError('Observational review authentication failed')
        intent = validate_intent(body['intent'], now_ns)
        _review(body['review'], intent, now_ns)
        if (canonical(intent) != canonical(expected_intent)
                or canonical(intent['usb_identity']) != canonical(current_usb_identity)
                or canonical(intent['references']) != canonical(current_references)):
            raise ValueError('Current observational intent, unit or references changed')
        return dict(intent_sha256=hashlib.sha256(canonical(intent)).hexdigest(),
            bundle_sha256=hashlib.sha256(raw).hexdigest(), verified_at_ns=now_ns,
            deadline_ns=intent['deadline_ns'], operator_id=body['review']['operator_id'],
            evidence_kind='HOST_AUTHENTICATED_OPERATOR_REPORT',
            physical_truth_verified=False, motion_authorized=False)
