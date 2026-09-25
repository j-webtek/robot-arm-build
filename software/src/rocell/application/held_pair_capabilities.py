"""Read-only declared capabilities and memory metrics, not firmware attestation."""
import hashlib
import base64
from .servo_diagnostic_http import DiagnosticHTTPReader
from .servo_start_authorization import _hex
from .wizard_diagnostic_coordinator import decode_diagnostic_json

PATH='/rocell/held-pair/capabilities'


def validate_pair_capabilities(raw, *, expected_boot):
    _hex(expected_boot,16)
    value=decode_diagnostic_json(raw,maximum=768)
    metrics={'free_internal_heap_bytes','minimum_free_internal_heap_bytes','largest_internal_block_bytes'}
    if (type(value) is not dict or set(value)!={'schema','boot_id','protocol','servo_id',
            'max_offset_counts','stack_measured','physical_accuracy_verified'}|metrics or
            value['schema']!='rocell.held_pair_capabilities.v1' or value['boot_id']!=expected_boot or
            value['protocol']!='hold-first-pair-v1' or type(value['servo_id']) is not int or value['servo_id']!=14 or
            type(value['max_offset_counts']) is not int or value['max_offset_counts']!=16 or
            value['stack_measured'] is not False or value['physical_accuracy_verified'] is not False or
            any(type(value[name]) is not int or not 0<=value[name]<=2**32-1 for name in metrics)):
        raise ValueError('Unsupported or mismatched pair capability report')
    # Sequential heap samples are not an atomic snapshot; do not infer allocation
    # guarantees or compare them as if sampled at the exact same instant.
    return dict(capabilities=value,response_sha256=hashlib.sha256(raw).hexdigest(),
                response_base64=base64.b64encode(raw).decode('ascii'),
                firmware_identity_verified=False,resource_sufficiency_verified=False,
                progression_authority=False,provenance_verified=False)


def read_pair_capabilities(*, address, expected_boot, port=80):
    """One GET only; no prepare/start request, filesystem changes or fallback."""
    _hex(expected_boot,16)
    reader=DiagnosticHTTPReader(address,port)
    raw=reader._get(PATH,maximum_bytes=768,timeout_seconds=3.0)
    return validate_pair_capabilities(raw,expected_boot=expected_boot)
