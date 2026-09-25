"""Bounded offline diagnostic ingestion; no device access or dispatch authority."""
import hashlib
from .wizard_diagnostic_coordinator import decode_diagnostic_json
from .servo_diagnostic_contract import assess_trace

MAX_TRACE_BYTES=1024*1024


def decode_trace(raw):
    """Preserve exact-byte identity and assess the declared v1/v2 structure.

The hash proves byte identity, not device authorship. Unknown fields are rejected
so a future producer cannot silently change semantics or embed configuration data.
"""
    if type(raw) is not bytes or not raw or len(raw)>MAX_TRACE_BYTES:
        raise ValueError('Nonempty bounded trace bytes required')
    try:
        trace=decode_diagnostic_json(raw,maximum=MAX_TRACE_BYTES)
        _fields(trace,{'schema','origin','command','dispatch','samples','policy'})
        _fields(trace['command'],{'boot_id','command_id','servo_id','joint',
            'conversion_version','angle_units','position_units','desired_rad','wire_rad',
            'desired_count','wire_count','payload','payload_sha256'})
        _fields(trace['dispatch'],{'boot_id','command_id','servo_id','wire_count',
            'speed','acceleration','device_us','bus_write_status'})
        v2=trace['schema']=='rocell.servo_diagnostic_trace.v2'
        policy_fields={'tolerance_counts','settle_us','maximum_gap_us'}
        if v2:policy_fields.add('maximum_pair_us')
        _fields(trace['policy'],policy_fields)
        if type(trace['samples']) is not list or len(trace['samples'])>2000:
            raise ValueError('Bounded sample list required')
        for sample in ([] if v2 else trace['samples']):
            _fields(sample,{'boot_id','command_id','servo_id','sequence',
                'read_started_us','read_finished_us','position_read_status',
                'position_count','target_read_status','target_count'})
        if v2:
            from .servo_diagnostic_v2 import assess_trace_v2
            assessment=assess_trace_v2(trace)
        else:assessment=assess_trace(trace)
    except (ValueError,TypeError,KeyError,AttributeError,RecursionError,OverflowError):
        # Do not echo raw payloads into UI/log exceptions.
        raise ValueError('Invalid servo diagnostic trace') from None
    return dict(trace=trace,assessment=assessment,raw_sha256=hashlib.sha256(raw).hexdigest(),
        raw_bytes=len(raw),provenance_verified=False,motion_authorized=False)


def _fields(value,expected):
    if type(value) is not dict or set(value)!=expected:
        raise ValueError('Exact versioned fields required')
