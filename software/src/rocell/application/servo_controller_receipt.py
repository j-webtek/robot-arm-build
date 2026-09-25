"""Correlate controller receipt with exact sent bytes and dispatch, offline only."""
import hashlib
import math
from .wizard_diagnostic_coordinator import decode_diagnostic_json


def assess_controller_receipt(receipt, sent_bytes, dispatch):
    fields={'schema','boot_id','command_id','received_us','payload_utf8','joint',
            'received_rad','received_rad_text','speed','acceleration'}
    if type(receipt) is not dict or set(receipt)!=fields or receipt['schema']!='rocell.controller_receipt.v1':
        raise ValueError('Invalid controller receipt')
    if type(sent_bytes) is not bytes or not 1<=len(sent_bytes)<=256:
        raise ValueError('Bounded sent command required')
    if type(receipt['payload_utf8']) is not str or receipt['payload_utf8'].encode('utf-8')!=sent_bytes:
        raise ValueError('Controller receipt differs from sent bytes')
    payload=decode_diagnostic_json(sent_bytes,maximum=256)
    if type(payload) is not dict or set(payload)!={'T','joint','rad','spd','acc'}:
        raise ValueError('Unsupported command payload')
    for field,expected in (('T',101),('joint',3)):
        if type(payload[field]) is not int or payload[field]!=expected:
            raise ValueError('Unsupported command kind')
    for field,maximum,record_field in (('spd',65535,'speed'),('acc',255,'acceleration')):
        if (type(payload[field]) is not int or not 1<=payload[field]<=maximum
                or type(receipt[record_field]) is not int or receipt[record_field]!=payload[field]
                or type(dispatch.get(record_field)) is not int or dispatch[record_field]!=payload[field]):
            raise ValueError('Controller settings mismatch')
    for field in ('boot_id','command_id'):
        value=receipt[field]
        if (type(value) is not str or not 1<=len(value)<=128 or
                any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_.-' for c in value)
                or value!=dispatch.get(field)):
            raise ValueError('Controller identity mismatch')
    if type(receipt['joint']) is not int or receipt['joint']!=3 or type(dispatch.get('servo_id')) is not int or dispatch['servo_id']!=14:
        raise ValueError('Controller joint mapping mismatch')
    if (type(receipt['received_us']) is not int or type(dispatch.get('device_us')) is not int
            or not 0<=receipt['received_us']<=dispatch['device_us']<=2**63-1):
        raise ValueError('Invalid receipt/dispatch chronology')
    if (type(payload['rad']) not in (int,float) or not math.isfinite(payload['rad'])
            or type(receipt['received_rad']) not in (int,float) or not math.isfinite(receipt['received_rad'])
            or type(receipt['received_rad_text']) is not str or not 1<=len(receipt['received_rad_text'])<=32):
        raise ValueError('Invalid parsed angle evidence')
    try:parsed=float(receipt['received_rad_text'])
    except ValueError:raise ValueError('Invalid parsed angle text') from None
    if not math.isfinite(parsed) or not math.isclose(parsed,receipt['received_rad'],rel_tol=1e-6,abs_tol=1e-12):
        raise ValueError('Contradictory parsed angle representations')
    # Report parser differences, never silently compensate them or assert that a
    # structural receipt proves a motor moved. Exact original bytes are primary.
    return dict(schema='rocell.controller_receipt_assessment.v1',
        sent_payload_sha256=hashlib.sha256(sent_bytes).hexdigest(),exact_payload_match=True,
        requested_rad=payload['rad'],controller_parsed_rad=parsed,
        parser_delta_rad=parsed-payload['rad'],progression_authority=False,
        physical_endpoint_verified=False)
