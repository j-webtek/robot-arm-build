"""Decode controller challenge publication; authenticity requires trusted transport."""
from .characterization_admission import encode_manifest
from .servo_start_authorization import _challenge_bytes, _hex


def decode_challenge(raw, *, expected_boot):
    _hex(expected_boot,16)
    if type(raw) is not bytes or not raw.startswith(b'RCCCHAL001\0') or len(raw)>224:
        raise ValueError('Invalid challenge framing')
    offset=11
    def take(n):
        nonlocal offset
        if offset+n>len(raw):raise ValueError('Truncated challenge')
        value=raw[offset:offset+n];offset+=n;return value
    def number(n):return int.from_bytes(take(n),'big')
    boot=take(16).hex();nonce=take(32).hex();campaign=take(32).hex();reference=take(32).hex()
    challenge=dict(schema='rocell.start_challenge.v1',boot_id=boot,nonce=nonce,
                   issued_us=number(8),expires_us=number(8))
    legs=number(1);budget=number(8)
    if boot!=expected_boot or not 1<=legs<=12:raise ValueError('Boot or leg mismatch')
    manifest=dict(maximum_us=budget,bounds=[[number(2),number(2)] for _ in range(7)],
                  goals=[[number(2),number(2)] for _ in range(legs)])
    if offset!=len(raw):raise ValueError('Trailing challenge data')
    _challenge_bytes(challenge);encode_manifest(manifest,campaign=campaign,reference=reference)
    return dict(challenge=challenge,manifest=manifest,campaign=campaign,reference=reference)
