"""Frozen initial-pair contract; no transport, key loading or automatic signing."""
from dataclasses import dataclass
import hashlib
import hmac
import struct
from .first_motion_contract import canonical
from .hold_bound_replay import _policy
from .servo_diagnostic_contract import _identifier
from .servo_start_authorization import DOMAIN, _hex, _key, _challenge_bytes
from .wizard_diagnostic_coordinator import decode_diagnostic_json


@dataclass(frozen=True)
class HeldPairPlan:
    encoded: bytes
    policy_encoded: bytes


def freeze_held_pair_plan(policy, *, boot_id, hold_plan_sha256,
                          forward_command_id, return_command_id,
                          offset_counts=6, tolerance_counts=2):
    _policy(policy)
    _hex(boot_id, 16)
    _hex(hold_plan_sha256, 32)
    _identifier(forward_command_id)
    _identifier(return_command_id)
    if (forward_command_id == return_command_id or type(offset_counts) is not int or
            type(tolerance_counts) is not int or not 0 <= tolerance_counts <= 2 or
            not 2*tolerance_counts < abs(offset_counts) <= 16):
        raise ValueError('Distinct commands and bounded nonoverlapping legs required')
    policy_bytes = canonical(policy)
    return HeldPairPlan(canonical(dict(schema='rocell.held_pair_plan.v1',
        origin='DEVICE_CAPTURE', boot_id=boot_id, hold_plan_sha256=hold_plan_sha256,
        forward_command_id=forward_command_id, return_command_id=return_command_id,
        offset_counts=offset_counts, tolerance_counts=tolerance_counts,
        policy_sha256=hashlib.sha256(policy_bytes).hexdigest())), policy_bytes)


def sign_held_pair(plan, challenge, key, *, approved_policy, expected_hold_plan_sha256):
    """Low-level signer; caller must establish hold/export admission first.

    Never log returned bytes. No wizard, CLI or hardware workflow exposes this
    function yet. DEVICE_CAPTURE is a protocol intent, not provenance evidence.
    """
    _key(key)
    header = _challenge_bytes(challenge)
    if type(plan) is not HeldPairPlan or type(plan.encoded) is not bytes:
        raise ValueError('Frozen pair plan required')
    doc = decode_diagnostic_json(plan.encoded, maximum=1536)
    if type(doc) is not dict or not {'forward_command_id', 'return_command_id',
                                   'offset_counts', 'tolerance_counts'} <= doc.keys():
        raise ValueError('Pair plan fields missing')
    expected = freeze_held_pair_plan(approved_policy, boot_id=challenge['boot_id'],
        hold_plan_sha256=expected_hold_plan_sha256,
        forward_command_id=doc['forward_command_id'], return_command_id=doc['return_command_id'],
        offset_counts=doc['offset_counts'], tolerance_counts=doc['tolerance_counts'])
    if plan != expected:
        raise ValueError('Pair plan differs from approved boot, hold or policy')
    unsigned = DOMAIN + header + struct.pack('>H', len(plan.encoded)) + plan.encoded
    return unsigned + hmac.digest(key, unsigned, 'sha256')
