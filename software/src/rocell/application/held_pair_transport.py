"""Bounded read-only pair collection; no command, retry or progression authority."""
import hashlib
import math
from .servo_diagnostic_http import DiagnosticHTTPReader
from .servo_start_authorization import _hex
from .held_evidence_digest import held_evidence_digest
from .held_leg_raw_export import SCHEMAS
from .wizard_diagnostic_coordinator import decode_diagnostic_json

STATUS='/rocell/held-pair/status'
RECORD='/rocell/held-pair/record?index='


class HeldPairHTTPReader(DiagnosticHTTPReader):
    def __call__(self,path,*,maximum_bytes,timeout_seconds):
        limit=1024 if path==STATUS else 9216
        allowed=type(path) is str and path in {STATUS,*(RECORD+str(i) for i in range(34))}
        if (self.failed or not allowed or
                type(maximum_bytes) is not int or not 1<=maximum_bytes<=limit or
                type(timeout_seconds) not in (int,float) or not math.isfinite(timeout_seconds) or
                not 0<timeout_seconds<=3):
            self.failed=True
            raise ValueError('Unsupported pair read or faulted reader')
        return self._get(path,maximum_bytes=maximum_bytes,timeout_seconds=timeout_seconds)


def collect_held_pair_snapshot(get_bytes,*,expected_boot,expected_session,expected_plan,leg):
    for value,size in [(expected_boot,16),(expected_session,32),(expected_plan,32)]:
        _hex(value,size)
    if leg not in ('forward','return'):
        raise ValueError('Expected named leg')
    responses,rows=[],[]
    result=dict(category='INCONCLUSIVE',stable_status_observed=False,provenance_verified=False,
                progression_authority=False,responses=responses,records=rows)
    identity=dict(boot_id=expected_boot,session_sha256=expected_session,plan_sha256=expected_plan,leg=leg)
    def read(path,maximum):
        raw=get_bytes(path,maximum_bytes=maximum,timeout_seconds=3.0)
        if type(raw) is not bytes or not 0<len(raw)<=maximum:
            raise ValueError('Invalid response budget')
        responses.append(dict(path=path,raw=raw,sha256=hashlib.sha256(raw).hexdigest()))
        value=decode_diagnostic_json(raw,maximum=maximum)
        if type(value) is not dict or any(value.get(k)!=v for k,v in identity.items()):
            raise ValueError('Response identity mismatch')
        return value
    def status():
        value=read(STATUS,1024)
        if (set(value)!=set(identity)|{'schema','state','reason','records','record_bytes','storage_fault','durable_export_verified'} or
                value['schema']!='rocell.held_pair_transport.v1' or
                value['state'] not in ('AWAITING_EXPORT','COMPLETE','STOPPED') or
                type(value['records']) is not int or not 0<=value['records']<=34 or
                type(value['record_bytes']) is not int or value['record_bytes']!=4096 or
                type(value['storage_fault']) is not bool or value['storage_fault'] or
                value['durable_export_verified'] is not False or
                (value['state']=='AWAITING_EXPORT' and leg!='forward') or
                (value['state']=='COMPLETE' and leg!='return')):
            raise ValueError('Unsupported, active or faulted store status')
        return value
    try:
        before=status();result['status']=before
        command=None
        for index in range(before['records']):
            item=read(RECORD+str(index),9216)
            if (set(item)!=set(identity)|{'schema','index','kind','raw_json'} or
                    item['schema']!='rocell.held_pair_record.v1' or type(item['index']) is not int or
                    item['index']!=index or item['kind'] not in SCHEMAS or type(item['raw_json']) is not str):
                raise ValueError('Invalid record envelope')
            raw=item['raw_json'].encode('utf-8')
            held_evidence_digest([(item['kind'],raw)])  # Bounds and NUL checks.
            body=decode_diagnostic_json(raw,maximum=4095)
            if (type(body) is not dict or body.get('schema')!=SCHEMAS[item['kind']] or
                    body.get('boot_id')!=expected_boot or type(body.get('command_id')) is not str):
                raise ValueError('Raw record identity mismatch')
            if command is None:command=body['command_id']
            if body['command_id']!=command:raise ValueError('Mixed command IDs')
            rows.append((item['kind'],raw))
        if status()!=before:raise ValueError('Capture changed while reading')
        if not rows:raise ValueError('Empty capture')
        result.update(category='TRANSPORT_CAPTURED',stable_status_observed=True,
                      evidence_sha256=held_evidence_digest(rows))
    except (ValueError,TypeError,KeyError,OSError,UnicodeError,RecursionError):
        result['reason']='INCOMPLETE_INVALID_OR_CHANGED_PAIR_TRANSPORT'
    return result
