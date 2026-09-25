"""Offline signer for the controller-bound shoulder session; never sends commands."""
import hmac
import json
import re
import struct

from .servo_start_authorization import DOMAIN, _challenge_bytes, _key


def sign_shoulder_start(challenge, command, scope, key):
    """Authenticate exact scope; this is not clearance or deployment approval."""
    _key(key)
    header = _challenge_bytes(challenge)
    if not isinstance(command, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,128}', command):
        raise ValueError('Restricted command identifier required')
    if scope not in ('PRELOAD_ONLY', 'PAIR_HOLD', 'MIXED_TARGET', 'POSE_PREPARATION', 'SHOULDER_RISE', 'CLEARANCE_RECOVERY', 'STABLE_CLEARANCE_RECOVERY'):
        raise ValueError('Explicit shoulder scope required')
    plan = json.dumps(dict(schema='rocell.shoulder_start.v1',
        boot_id=challenge['boot_id'], command_id=command, scope=scope),
        separators=(',', ':')).encode('ascii')
    unsigned = DOMAIN + header + struct.pack('>H', len(plan)) + plan
    return unsigned + hmac.digest(key, unsigned, 'sha256')
