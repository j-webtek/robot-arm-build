"""Offline reference contract for authenticated, single-use diagnostic start.

This module neither provisions keys nor sends requests. Native verification,
clearance admission and an authorized deployment are required before exposure.
"""
import base64
import hashlib
import hmac
import secrets
import struct

from .servo_session_plan import SessionPlan, freeze_session_plan

DOMAIN = b'rocell.diagnostic-start.v1\x00'
MAX_PLAN_BYTES = 16384
MAX_LEASE_US = 30_000_000


def _integer(value):
    if type(value) is not int or not 0 <= value <= 2**63-1:
        raise ValueError('Invalid controller monotonic time')
    return value


def _hex(value, length):
    if (type(value) is not str or len(value) != length * 2
            or any(char not in '0123456789abcdef' for char in value)):
        raise ValueError('Invalid authorization identity')
    return bytes.fromhex(value)


def _key(key):
    if type(key) is not bytes or len(key) != 32 or key == bytes(32):
        raise ValueError('Dedicated 32-byte authorization key required')


def issue_challenge(boot_id, issued_us, *, lease_us=MAX_LEASE_US):
    """Reference controller behavior; time must come from its monotonic clock."""
    _hex(boot_id, 16); _integer(issued_us)
    if type(lease_us) is not int or not 1 <= lease_us <= MAX_LEASE_US:
        raise ValueError('Invalid challenge lifetime')
    expires = _integer(issued_us + lease_us)
    return dict(schema='rocell.start_challenge.v1', boot_id=boot_id,
        nonce=secrets.token_hex(32), issued_us=issued_us, expires_us=expires)


def _challenge_bytes(challenge):
    if (type(challenge) is not dict or set(challenge) !=
            {'schema', 'boot_id', 'nonce', 'issued_us', 'expires_us'}
            or challenge['schema'] != 'rocell.start_challenge.v1'):
        raise ValueError('Exact challenge required')
    issued = _integer(challenge['issued_us']); expires = _integer(challenge['expires_us'])
    if not 1 <= expires-issued <= MAX_LEASE_US:
        raise ValueError('Invalid challenge lifetime')
    return (_hex(challenge['boot_id'], 16) + _hex(challenge['nonce'], 32)
            + struct.pack('>QQ', issued, expires))


def _validate_plan(plan, boot_id):
    if type(plan) is not SessionPlan or not 1 <= len(plan.encoded) <= MAX_PLAN_BYTES:
        raise ValueError('Bounded frozen session plan required')
    document = plan.to_dict()
    if document.get('schema') not in ('rocell.session_plan.v2','rocell.session_plan.v3'):
        raise ValueError('Start requires baseline-bound plan')
    sent = base64.b64decode(document['sent_base64'], validate=True)
    rebuilt = freeze_session_plan(document['command'], document['policy'], sent,
        document['schedule'], origin=document['origin'], baseline_policy=document['baseline_policy'],
        whole_arm_policy=document.get('whole_arm_policy'))
    if rebuilt.encoded != plan.encoded or document['command']['boot_id'] != boot_id:
        raise ValueError('Noncanonical or wrong-boot plan')
    return document


def sign_start(plan, challenge, key):
    """Sign exact plan bytes. Never log the returned authorization token or key."""
    _key(key)
    header = _challenge_bytes(challenge)
    _validate_plan(plan, challenge['boot_id'])
    unsigned = DOMAIN + header + struct.pack('>H', len(plan.encoded)) + plan.encoded
    return unsigned + hmac.digest(key, unsigned, 'sha256')


class StartAuthorizationGate:
    """Reference single-owner state machine; no movement authority is granted.

    A terminal attempt consumes the gate before parsing or returning. Admission,
    export failure or lost replies must never refund it. The native implementation
    must serialize ingress through its owner and preserve this ordering.
    """

    def __init__(self, challenge, key, *, expected_origin='DEVICE_CAPTURE'):
        _key(key)
        if expected_origin not in ('SIMULATION', 'DEVICE_CAPTURE'):
            raise ValueError('Explicit execution origin required')
        self._header = _challenge_bytes(challenge)
        self._boot = challenge['boot_id']
        self._issued = challenge['issued_us']; self._expires = challenge['expires_us']
        self._key = key
        self._origin = expected_origin
        self._used = False

    def consume(self, token, *, now_us):
        if self._used:
            raise ValueError('Start authorization already consumed')
        self._used = True
        now = _integer(now_us)
        if not self._issued <= now < self._expires:
            raise ValueError('Start challenge expired or clock invalid')
        prefix = DOMAIN + self._header
        minimum = len(prefix) + 2 + 1 + 32
        if type(token) is not bytes or not minimum <= len(token) <= minimum-1+MAX_PLAN_BYTES:
            raise ValueError('Invalid start envelope size')
        unsigned, signature = token[:-32], token[-32:]
        if not hmac.compare_digest(signature, hmac.digest(self._key, unsigned, 'sha256')):
            raise ValueError('Start authentication failed')
        if unsigned[:len(prefix)] != prefix:
            raise ValueError('Start challenge mismatch')
        offset = len(prefix)
        length = struct.unpack('>H', unsigned[offset:offset+2])[0]
        encoded = unsigned[offset+2:]
        if length != len(encoded):
            raise ValueError('Start plan length mismatch')
        plan = SessionPlan(encoded)
        document = _validate_plan(plan, self._boot)
        if document['origin'] != self._origin:
            raise ValueError('Start execution origin mismatch')
        return dict(schema='rocell.start_authorization_assessment.v1',
            session_plan_sha256=hashlib.sha256(encoded).hexdigest(),
            command_id=document['command']['command_id'], boot_id=self._boot,
            authenticated_request=True, consumed=True, progression_authority=False,
            clearance_verified=False, write_attempted=False)
