"""Offline signer for exact bounded manifests; no transport or live admission."""
import hmac
from .servo_start_authorization import DOMAIN, _challenge_bytes, _key, _hex


def encode_manifest(manifest, *, campaign, reference):
    if type(manifest) is not dict or set(manifest) != {'goals', 'bounds', 'maximum_us'}:
        raise ValueError('Exact manifest fields required')
    goals, bounds, budget = manifest['goals'], manifest['bounds'], manifest['maximum_us']
    if type(goals) is not list or not 1 <= len(goals) <= 12 or type(bounds) is not list or len(bounds) != 7:
        raise ValueError('Bounded goals and seven bounds required')
    if type(budget) is not int or not 0 < budget <= 60000000:
        raise ValueError('Invalid campaign budget')
    for pair in goals + bounds:
        if type(pair) is not list or len(pair) != 2 or any(type(v) is not int or not 0 <= v <= 4095 for v in pair):
            raise ValueError('Integer count pairs required')
    if any(lo > hi for lo, hi in bounds):
        raise ValueError('Invalid bounds')
    for i, pair in enumerate(goals):
        if sum(pair) != 4114 or any(not bounds[j+1][0] <= pair[j] <= bounds[j+1][1] for j in range(2)):
            raise ValueError('Invalid coupled goal')
        if i and not 1 <= abs(pair[0]-goals[i-1][0]) <= 24:
            raise ValueError('Invalid step')
    return (b'RCCADMIT01\0' + _hex(campaign, 32) + _hex(reference, 32)
            + bytes([len(goals)]) + budget.to_bytes(8, 'big')
            + b''.join(v.to_bytes(2, 'big') for pair in bounds+goals for v in pair)
            + b'\x00\x14\x01')


def sign_campaign(manifest, challenge, key, *, campaign, reference):
    """Sign offline only. Do not log keys/tokens; fresh physical checks remain required."""
    _key(key)
    payload = encode_manifest(manifest, campaign=campaign, reference=reference)
    unsigned = DOMAIN + _challenge_bytes(challenge) + len(payload).to_bytes(2, 'big') + payload
    return unsigned + hmac.digest(key, unsigned, 'sha256')
