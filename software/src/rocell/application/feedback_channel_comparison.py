"""Offline comparison of retained HTTP/serial packets; no transport access.

Agreement is not proof of encoder freshness: both interfaces may read the same
controller cache. Preserve original packet hashes and acquisition intervals.
"""
import base64
import hashlib
import math
from rocell.arm.feedback import parse_feedback_line


def compare_feedback_channels(http, serial):
    packets=[]
    for sample,kind in ((http,'HTTP'),(serial,'SERIAL')):
        if sample.get('channel')!=kind:
            raise ValueError('Explicit distinct channel labels required')
        begin=sample.get('started_ns');end=sample.get('finished_ns')
        if type(begin) is not int or type(end) is not int or not 0<begin<=end:
            raise ValueError('Host monotonic capture interval required')
        raw=base64.b64decode(sample['response_base64'],validate=True)
        if not 0<len(raw)<=16384 or hashlib.sha256(raw).hexdigest()!=sample['response_sha256']:
            raise ValueError('Bounded hash-verified original packet required')
        # HTTP bodies need no line terminator; serial evidence must retain it.
        # Hash the original bytes above, not this parsing-only normalization.
        parsed=parse_feedback_line(raw+b'\n' if kind=='HTTP' and not raw.endswith(b'\n') else raw)
        values=parsed.raw_fields
        q=[values.get(k) for k in ('b','s','e','t','r','g')]
        if any(type(v) not in (int,float) or not math.isfinite(v) for v in q):
            raise ValueError('Complete finite joint packet required')
        packets.append(q)
    gap=max(0,max(http['started_ns'],serial['started_ns'])-min(http['finished_ns'],serial['finished_ns']))
    residual=[b-a for a,b in zip(*packets)]
    nearby=gap<=1_000_000_000
    return dict(schema='rocell.feedback_channel_comparison.v1',
        status=('PACKETS_AGREE' if max(map(abs,residual))<=1e-8 else 'PACKETS_DIFFER') if nearby else 'CAPTURES_TOO_FAR_APART',
        serial_minus_http_rad=dict(zip(('b','s','e','t','r','g'),residual)),
        capture_interval_gap_ns=gap,
        sources=[dict(channel=s['channel'],sha256=s['response_sha256'],started_ns=s['started_ns'],finished_ns=s['finished_ns']) for s in (http,serial)],
        same_controller_identity_verified=False,stationary_interval_verified=False,
        encoder_freshness_verified=False,physical_accuracy_verified=False,
        motion_authorized=False)
