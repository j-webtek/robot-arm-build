"""Exact-byte hold transport exports and pure replay, including partial failures."""
import base64
import hashlib
from functools import partial
from pathlib import Path

from .first_motion_contract import canonical
from .hold_transport_snapshot import collect_hold_snapshot, collect_recovery_snapshot
from .product_ghost_export_review import _read
from .servo_start_authorization import _hex
from .wizard_diagnostic_export import WizardDiagnosticExporter


def capture_hold_transport(root, get_bytes, *, expected_boot):
    return _capture_transport(root, get_bytes, expected_boot=expected_boot, recovery=False)


def capture_recovery_transport(root, get_bytes, *, expected_boot, profile='supported'):
    return _capture_transport(root, get_bytes, expected_boot=expected_boot, recovery=True,profile=profile)


def _transport_profile(recovery,profile):
    if profile not in ('supported','six_count') or (not recovery and profile!='supported'):
        raise ValueError('Explicit reviewed transport profile required')
    if not recovery:return 'hold',collect_hold_snapshot
    return ('six_count_recovery' if profile=='six_count' else 'recovery',
            partial(collect_recovery_snapshot,profile=profile))


def _capture_transport(root, get_bytes, *, expected_boot, recovery, profile='supported'):
    label,collect=_transport_profile(recovery,profile)
    _hex(expected_boot, 16)
    root = Path(root).resolve()
    exporter = WizardDiagnosticExporter(root)
    exporter.prepare(create=True)  # Establish destination before the first GET.
    observed = []
    def read(path, *, maximum_bytes, timeout_seconds):
        try:
            raw = get_bytes(path, maximum_bytes=maximum_bytes, timeout_seconds=timeout_seconds)
        except (OSError, ValueError, TypeError):
            observed.append(dict(path=path, error='RECEIVE_FAILED'))
            raise ValueError('Retained receive failure') from None
        if type(raw) is not bytes or not raw or len(raw) > maximum_bytes:
            observed.append(dict(path=path, error='INVALID_RESPONSE_SIZE_OR_TYPE'))
            raise ValueError('Invalid retained response size')
        observed.append(dict(path=path, sha256=hashlib.sha256(raw).hexdigest(),
                             base64=base64.b64encode(raw).decode('ascii')))
        return raw
    snapshot = collect(read, expected_boot=expected_boot)
    summary = {k: v for k, v in snapshot.items() if k != 'responses'}
    bundle = dict(schema=f'rocell.{label}_transport_export.v1', expected_boot=expected_boot,
                  responses=observed, summary=summary, progression_authority=False)
    receipt = exporter.export({'mode': f'read-only-{label}-transport'}, [],
        attachments={f'{label}-transport.json': canonical(bundle)})
    path = Path(receipt['path'])
    replay = (replay_recovery_transport_export(root,path.name,profile=profile) if recovery
              else replay_hold_transport_export(root,path.name))
    return dict(export_path=str(path), export_verified=True, replay_verified=replay['matches'],
                summary=summary, progression_authority=False)


def replay_hold_transport_export(root, export_id):
    bundle, _ = _read(Path(root).resolve(), export_id, 'attachment-hold-transport.json')
    return replay_hold_transport_bundle(bundle)


def replay_hold_transport_bundle(bundle):
    return _replay_transport_bundle(bundle, recovery=False)


def replay_recovery_transport_export(root, export_id, *, profile='supported'):
    label,_=_transport_profile(True,profile)
    bundle, _ = _read(Path(root).resolve(), export_id, f'attachment-{label}-transport.json')
    return replay_recovery_transport_bundle(bundle,profile=profile)


def replay_recovery_transport_bundle(bundle, *, profile='supported'):
    return _replay_transport_bundle(bundle, recovery=True,profile=profile)


def _replay_transport_bundle(bundle, *, recovery, profile='supported'):
    label,collect=_transport_profile(recovery,profile)
    fields = {'schema', 'expected_boot', 'responses', 'summary', 'progression_authority'}
    if (type(bundle) is not dict or set(bundle) != fields or
            bundle['schema'] != f'rocell.{label}_transport_export.v1' or
            bundle['progression_authority'] is not False or type(bundle['responses']) is not list or
            not 1 <= len(bundle['responses']) <= 14):
        raise ValueError('Invalid hold transport envelope')
    _hex(bundle['expected_boot'], 16)
    cursor, invalid = 0, False
    def read(path, *, maximum_bytes, timeout_seconds):
        nonlocal cursor, invalid
        try:
            if cursor >= len(bundle['responses']):
                raise ValueError('Missing response')
            item = bundle['responses'][cursor]
            cursor += 1
            if type(item) is not dict or item.get('path') != path:
                raise ValueError('Retained path mismatch')
            if set(item) == {'path', 'error'} and item['error'] in ('RECEIVE_FAILED', 'INVALID_RESPONSE_SIZE_OR_TYPE'):
                # Expected collection failure, not a corrupt export.
                raise OSError('Retained receive failure')
            if (set(item) != {'path', 'sha256', 'base64'} or type(item['base64']) is not str or
                    len(item['base64']) > 4*((maximum_bytes+2)//3)):
                raise ValueError('Retained response fields')
            raw = base64.b64decode(item['base64'], validate=True)
            if (not raw or len(raw) > maximum_bytes or hashlib.sha256(raw).hexdigest() != item['sha256'] or
                    base64.b64encode(raw).decode('ascii') != item['base64']):
                raise ValueError('Retained bytes mismatch')
            return raw
        except (ValueError, TypeError, KeyError, UnicodeError):
            invalid = True
            raise ValueError('Invalid retained transport evidence') from None
    snapshot = collect(read, expected_boot=bundle['expected_boot'])
    summary = {k: v for k, v in snapshot.items() if k != 'responses'}
    if invalid or cursor != len(bundle['responses']) or canonical(summary) != canonical(bundle['summary']):
        raise ValueError('Hold transport replay mismatch')
    return dict(matches=True, summary=summary, progression_authority=False)
