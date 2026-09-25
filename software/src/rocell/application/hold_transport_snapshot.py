"""Bounded read-only collection for hold_transport.v1; never sends commands."""
import hashlib
import math

from .servo_diagnostic_http import DiagnosticHTTPReader
from .servo_diagnostic_contract import _identifier
from .servo_start_authorization import _hex
from .servo_transport_snapshot import STATUS, RECORD
from .wizard_diagnostic_coordinator import decode_diagnostic_json

RECOVERY_STATUS = '/rocell/recovery/status'
RECOVERY_RECORD = '/rocell/recovery/record?index='


class RecoveryHTTPReader(DiagnosticHTTPReader):
    """Recovery GETs only; never falls back to ordinary diagnostic endpoints."""
    def __call__(self, path, *, maximum_bytes, timeout_seconds):
        allowed = path == RECOVERY_STATUS or (type(path) is str and
                    path in {RECOVERY_RECORD+str(i) for i in range(12)})
        if (self.failed or not allowed or type(maximum_bytes) is not int or
                not 1 <= maximum_bytes <= (512 if path == RECOVERY_STATUS else 4608) or
                type(timeout_seconds) not in (int, float) or not math.isfinite(timeout_seconds) or
                not 0 < timeout_seconds <= 3):
            self.failed = True
            raise ValueError('Unsupported recovery read or faulted reader')
        return self._get(path, maximum_bytes=maximum_bytes, timeout_seconds=timeout_seconds)


class HoldHTTPReader(DiagnosticHTTPReader):
    """Explicit hold-only GET budgets; legacy reader limits remain unchanged."""
    def __call__(self, path, *, maximum_bytes, timeout_seconds):
        allowed = path == STATUS or (type(path) is str and path in {RECORD+str(i) for i in range(12)})
        if (self.failed or not allowed or type(maximum_bytes) is not int or
                not 1 <= maximum_bytes <= (512 if path == STATUS else 4608) or
                type(timeout_seconds) not in (int, float) or not math.isfinite(timeout_seconds) or
                not 0 < timeout_seconds <= 3):
            self.failed = True
            raise ValueError('Unsupported hold read or faulted reader')
        return self._get(path, maximum_bytes=maximum_bytes, timeout_seconds=timeout_seconds)


def collect_hold_snapshot(get_bytes, *, expected_boot):
    return _collect_snapshot(get_bytes, expected_boot=expected_boot, recovery=False)


def collect_recovery_snapshot(get_bytes, *, expected_boot, profile='supported'):
    """Recovery-only schemas; no ordinary-hold fallback or movement authority."""
    return _collect_snapshot(get_bytes, expected_boot=expected_boot, recovery=True,profile=profile)


def _collect_snapshot(get_bytes, *, expected_boot, recovery, profile='supported'):
    """At most 14 GETs; partial raw responses survive errors. No retry or start.

    Stable transport collection is not endpoint verification or authenticated
    provenance. FAULT captures may intentionally lack a terminal record.
    """
    _hex(expected_boot, 16)
    if profile not in ('supported','six_count') or (not recovery and profile!='supported'):
        raise ValueError('Explicit reviewed transport profile required')
    prefix = f'rocell.{profile}_recovery_' if recovery else 'rocell.hold_'
    status_path, record_path = (RECOVERY_STATUS, RECOVERY_RECORD) if recovery else (STATUS, RECORD)
    retained, records = [], []
    result = dict(schema=prefix+'transport_snapshot.v1', expected_boot=expected_boot,
                  category='INCONCLUSIVE', stable_status_observed=False,
                  endpoint_assessed=False, provenance_verified=False, progression_authority=False,
                  responses=retained, records=records)
    def read(path, maximum):
        raw = get_bytes(path, maximum_bytes=maximum, timeout_seconds=3.0)
        if type(raw) is not bytes or not raw or len(raw) > maximum:
            raise ValueError('Invalid response budget')
        retained.append(dict(path=path, raw=raw, sha256=hashlib.sha256(raw).hexdigest()))
        value = decode_diagnostic_json(raw, maximum=maximum)
        if type(value) is not dict:
            raise ValueError('Response object required')
        return value
    def status():
        value = read(status_path, 512)
        fields = {'schema', 'instance_id', 'state', 'reason', 'records', 'record_bytes',
                  'storage_fault', 'durable_export_verified'}
        if (set(value) != fields or value['schema'] != prefix+'transport.v1' or
                value['instance_id'] != expected_boot or value['state'] not in ('IDLE', 'CAPTURED', 'FAULT') or
                type(value['records']) is not int or not 0 <= value['records'] <= 12 or
                type(value['record_bytes']) is not int or value['record_bytes'] != 4096 or
                type(value['storage_fault']) is not bool or value['durable_export_verified'] is not False):
            raise ValueError('Unsupported or active status')
        _identifier(value['reason'])
        if (value['state'] == 'IDLE' and value['records'] != 0 or
                value['state'] == 'CAPTURED' and (value['records'] not in ((8,) if recovery else (8, 11)) or value['storage_fault'])):
            raise ValueError('Contradictory hold status')
        return value
    try:
        before = status()
        result['status'] = before
        kinds = {'hold_auth': prefix+'authorization.v1', 'hold_scan': prefix+'snapshot.v1',
                 'hold_action': prefix+'action.v1', 'hold_terminal': prefix+'terminal.v1'}
        command = None
        for index in range(before['records']):
            item = read(record_path + str(index), 4608)
            if (set(item) != {'schema', 'instance_id', 'index', 'kind', 'record'} or
                    item['schema'] != prefix+'record.v1' or item['instance_id'] != expected_boot or
                    type(item['index']) is not int or item['index'] != index or
                    item['kind'] not in kinds or type(item['record']) is not dict):
                raise ValueError('Record envelope mismatch')
            body = item['record']
            if body.get('schema') != kinds[item['kind']] or body.get('boot_id') != expected_boot:
                raise ValueError('Record identity mismatch')
            cid = _identifier(body.get('command_id'))
            if index == 0:
                if item['kind'] != 'hold_auth':
                    raise ValueError('Authorization missing')
                command = cid
            if cid != command or index > 0 and item['kind'] == 'hold_auth':
                raise ValueError('Mixed commands')
            if item['kind'] == 'hold_terminal' and index != before['records'] - 1:
                raise ValueError('Terminal not last')
            records.append(body)
        after = status()
        if after != before:
            raise ValueError('Capture changed while reading')
        if before['state'] == 'CAPTURED' and (records[-1]['schema'] != prefix+'terminal.v1' or
                records[-1].get('state') != 'CAPTURED'):
            raise ValueError('Captured terminal missing')
        result.update(category='TRANSPORT_CAPTURED', stable_status_observed=True)
    except (ValueError, TypeError, KeyError, OSError, UnicodeError, RecursionError):
        result['reason'] = 'INCOMPLETE_INVALID_OR_CHANGED_TRANSPORT'
    return result
