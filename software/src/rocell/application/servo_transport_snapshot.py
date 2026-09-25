"""Read-only bounded collection of candidate diagnostic transport records.

The supplied get_bytes(path, maximum_bytes=..., timeout_seconds=...) must enforce
its byte/time budget while receiving, reject redirects/non-200 responses, and
never retry. No network adapter is constructed here. v2 binds boot instance across
responses; legacy v1 status lacks that identity. In either version,
stable retrieval is NOT authenticated provenance or permission to move.
"""
import hashlib
from .wizard_diagnostic_coordinator import decode_diagnostic_json

STATUS = '/rocell/diagnostics/status'
RECORD = '/rocell/diagnostics/record?index='


def collect_snapshot(get_bytes, *, startup=False):
    retained = []

    def read(path, maximum):
        raw = get_bytes(path, maximum_bytes=maximum, timeout_seconds=3.0)
        if type(raw) is not bytes or not raw or len(raw) > maximum:
            raise ValueError('Invalid bounded transport response')
        try:
            value = decode_diagnostic_json(raw, maximum=maximum)
        except (ValueError, TypeError, RecursionError, UnicodeError):
            raise ValueError('Invalid transport JSON') from None
        if type(value) is not dict:
            raise ValueError('Transport object required')
        retained.append(dict(path=path, raw=raw, sha256=hashlib.sha256(raw).hexdigest()))
        return value

    def status():
        value = read(STATUS, 512)
        fields = {'schema','state','reason','records','storage_fault',
                  'start_supported','durable_export_verified'}
        v3=value.get('schema')=='rocell.diagnostic_transport.v3'
        v2=value.get('schema') in ('rocell.diagnostic_transport.v2','rocell.diagnostic_transport.v3')
        if v2:fields.add('instance_id')
        if v2 and (type(value.get('instance_id')) is not str or len(value['instance_id'])!=32
                   or any(c not in '0123456789abcdef' for c in value['instance_id'])):
            raise ValueError('Invalid boot instance identity')
        if (set(value) != fields or value['schema'] not in ('rocell.diagnostic_transport.v1','rocell.diagnostic_transport.v2','rocell.diagnostic_transport.v3')
                or value['state'] not in ('IDLE','CAPTURED','FAULT')
                or type(value['records']) is not int or not 0 <= value['records'] <= 16
                or type(value['storage_fault']) is not bool
                or value['start_supported'] is not v3
                or value['durable_export_verified'] is not False
                or type(value['reason']) is not str or len(value['reason']) > 64):
            raise ValueError('Unsupported or nonterminal diagnostic status')
        if value['state'] == 'IDLE' and value['records'] != 0:
            raise ValueError('Idle session has unexpected evidence')
        if value['state'] == 'CAPTURED' and (value['records'] < 5 or value['storage_fault']):
            raise ValueError('Contradictory captured status')
        return value

    before = status()
    v2=before['schema'] in ('rocell.diagnostic_transport.v2','rocell.diagnostic_transport.v3')
    records = []
    prefix=(('startup_auth','startup_first','startup_second','startup_control',
             'receipt','converted','hook','dispatch','write') if startup else
            ('converted','hook','dispatch','write'))
    if startup and before['schema']!='rocell.diagnostic_transport.v3':
        raise ValueError('Startup requires explicit boot-bound start-capable transport')
    for index in range(before['records']):
        value = read(RECORD+str(index), 2304)
        if not startup and index==0 and value.get('kind')=='authorization':
            if not v2:raise ValueError('Authorization requires boot-bound transport')
            prefix=('authorization','receipt','baseline','converted','hook','dispatch','write')
        if index==1 and prefix[0]=='authorization' and value.get('kind')=='whole_arm':
            prefix=('authorization','whole_arm','receipt','baseline','converted','hook','dispatch','write')
        if not startup and index==0 and value.get('kind')=='receipt':prefix=('receipt',)+prefix
        if index==1 and prefix[0]=='receipt' and value.get('kind')=='baseline':
            prefix=('receipt','baseline','converted','hook','dispatch','write')
        fields={'schema','index','kind','record'}
        if v2:fields.add('instance_id')
        if v2 and value.get('instance_id')!=before['instance_id']:
            raise ValueError('Controller instance changed during collection')
        if (set(value) != fields
                or value['schema'] != ('rocell.diagnostic_record.v2' if v2 else 'rocell.diagnostic_record.v1')
                or type(value['index']) is not int or value['index'] != index
                or value['kind'] != (prefix[index] if index < len(prefix) else 'pair')
                or type(value['record']) is not dict):
            raise ValueError('Missing, reordered or unsupported diagnostic record')
        records.append(value)
    after = status()
    if before != after:
        raise ValueError('Diagnostic session changed during collection')
    retained_records=records
    if startup:
        if records:
            authorization=records[0]['record']
            if authorization.get('boot_id')!=before['instance_id'] or not authorization.get('command_id'):
                raise ValueError('Startup authorization identity mismatch')
            for item in records[1:4]:
                body=item['record']
                key='scan_id' if item['kind'] in ('startup_first','startup_second') else 'command_id'
                if body.get('boot_id')!=before['instance_id'] or body.get(key)!=authorization['command_id']:
                    raise ValueError('Startup acquisition identity mismatch')
            if len(records)>4 and any(records[4]['record'].get(key)!=authorization[key]
                                      for key in ('boot_id','command_id')):
                raise ValueError('Startup receipt identity mismatch')
        records=records[4:];prefix=prefix[4:]
    if prefix[0]=='authorization':
        authorization=records[0]['record']
        if (authorization.get('boot_id')!=before['instance_id'] or not authorization.get('command_id')):
            raise ValueError('Authorization identity mismatch')
        if len(records)>1 and any(records[1]['record'].get(key)!=authorization[key]
                                 for key in ('boot_id','command_id')):
            raise ValueError('Authorization/receipt identity mismatch')
        records=records[1:];prefix=prefix[1:]
        if prefix[0]=='whole_arm':
            if len(records)>1 and any(records[1]['record'].get(key)!=authorization[key]
                                     for key in ('boot_id','command_id')):
                raise ValueError('Whole-arm/receipt identity mismatch')
            records=records[1:];prefix=prefix[1:]
    # Check contextual identity wherever the current producer supplies it. The
    # hook record lacks identity; its association remains positional in v1.
    has_baseline='baseline' in prefix
    shift=2 if has_baseline else 1 if prefix[0]=='receipt' else 0
    if before['state']=='CAPTURED' and len(records)<len(prefix)+1:
        raise ValueError('Captured session lacks acquisitions')
    if shift and records and (not records[0]['record'].get('boot_id') or not records[0]['record'].get('command_id')):
        raise ValueError('Missing receipt identity')
    if has_baseline and len(records)>1:
        baseline=records[1]['record'].get('acquisition')
        if type(baseline) is not dict:raise ValueError('Missing baseline acquisition')
        for name in ('target','feedback'):
            part=baseline.get(name)
            if (type(part) is not dict or part.get('servo_id')!=14 or
                    any(part.get(k)!=records[0]['record'][k] for k in ('boot_id','command_id'))):
                raise ValueError('Baseline identity mismatch')
    if len(records)>shift:
        identity = records[shift]['record']
        if shift and any(records[0]['record'].get(k)!=identity.get(k) for k in ('boot_id','command_id')):
            raise ValueError('Receipt identity mismatch')
        for key in ('boot_id','command_id','servo_id'):
            if key not in identity:
                raise ValueError('Missing diagnostic identity')
        for item in records[shift+2:]:
            body = item['record']
            parts = (body.get('target'),body.get('feedback')) if item['kind']=='pair' else (body,)
            for part in parts:
                if type(part) is not dict or any(part.get(k)!=identity[k] for k in ('boot_id','command_id','servo_id')):
                    raise ValueError('Diagnostic identity mismatch')
    return dict(schema='rocell.transport_snapshot.v1',status=before,records=retained_records,
                responses=retained,stable_status_observed=True,instance_identity_bound=v2,provenance_verified=False,
                progression_authority=False,endpoint_assessed=False)
