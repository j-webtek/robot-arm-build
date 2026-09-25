"""Frozen hold-policy contract and signing; no network, provisioning or motion."""
from dataclasses import dataclass
import hashlib
import hmac
import struct

from .first_motion_contract import canonical
from .hold_bound_replay import _policy
from .servo_diagnostic_contract import _identifier
from .servo_start_authorization import DOMAIN, _challenge_bytes, _hex, _key
from .wizard_diagnostic_coordinator import decode_diagnostic_json


@dataclass(frozen=True)
class HoldPlan:
    encoded: bytes
    policy_encoded: bytes


def freeze_hold_plan(policy, *, boot_id, command_id):
    _policy(policy)
    _hex(boot_id, 16)
    _identifier(command_id)
    policy_bytes = canonical(policy)
    encoded = canonical(dict(schema='rocell.hold_plan.v1', boot_id=boot_id,
        command_id=command_id, origin='DEVICE_CAPTURE',
        policy_sha256=hashlib.sha256(policy_bytes).hexdigest()))
    return HoldPlan(encoded, policy_bytes)


def validate_hold_plan(plan, *, boot_id, approved_policy):
    if type(plan) is not HoldPlan or type(plan.encoded) is not bytes or type(plan.policy_encoded) is not bytes:
        raise ValueError('Frozen hold plan required')
    _policy(approved_policy)
    document = decode_diagnostic_json(plan.encoded, maximum=1536)
    if type(document) is not dict or 'command_id' not in document:
        raise ValueError('Hold plan identity missing')
    expected = freeze_hold_plan(approved_policy, boot_id=boot_id, command_id=document['command_id'])
    if plan != expected:
        raise ValueError('Noncanonical, wrong-boot or policy-mismatched hold plan')
    return document


def sign_hold(plan, challenge, key, *, approved_policy):
    """Never export/log the returned token. Native one-use admission is mandatory."""
    _key(key)
    header = _challenge_bytes(challenge)
    validate_hold_plan(plan, boot_id=challenge['boot_id'], approved_policy=approved_policy)
    unsigned = DOMAIN + header + struct.pack('>H', len(plan.encoded)) + plan.encoded
    return unsigned + hmac.digest(key, unsigned, 'sha256')
