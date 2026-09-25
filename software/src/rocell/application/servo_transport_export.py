"""Exact-byte transport capture/export/replay; no network construction or motion.

Successful export proves retained response identity and collection consistency,
not device authorship, servo behavior, or endpoint accuracy.
"""
import base64
import hashlib
from pathlib import Path
from .first_motion_contract import canonical
from .servo_transport_snapshot import collect_snapshot
from .wizard_diagnostic_export import WizardDiagnosticExporter, verify_export
from .product_ghost_export_review import _read


def _summary(snapshot):
    return {key:value for key,value in snapshot.items() if key != 'responses'}


def capture_transport_export(export_root, get_bytes, *, startup=False):
    # Establish the destination before any read; never issue control commands if
    # export fails. The injected reader is restricted by collect_snapshot.
    exporter=WizardDiagnosticExporter(Path(export_root).resolve())
    exporter.prepare(create=True)
    observed=[]
    def retain_get(path,*,maximum_bytes,timeout_seconds):
        try:
            raw=get_bytes(path,maximum_bytes=maximum_bytes,timeout_seconds=timeout_seconds)
        except (OSError,ValueError,TypeError):
            observed.append(dict(path=path,error='RECEIVE_FAILED'))
            raise ValueError('Bounded receive failed') from None
        if type(raw) is not bytes or not raw or len(raw)>maximum_bytes:
            observed.append(dict(path=path,error='INVALID_RESPONSE_SIZE_OR_TYPE'))
            raise ValueError('Invalid bounded response')
        observed.append(dict(path=path,sha256=hashlib.sha256(raw).hexdigest(),
            base64=base64.b64encode(raw).decode('ascii')))
        return raw
    try:
        snapshot=collect_snapshot(retain_get if startup else get_bytes, startup=startup)
    except (ValueError,KeyError,TypeError,OverflowError,RecursionError):
        if not startup:raise
        # Save only bounded diagnostic response bodies, not arbitrary exception
        # messages, tokens or headers. Never retry a failed collection.
        bundle=dict(schema='rocell.startup_transport_failure.v1',responses=observed,
            summary=dict(status='COLLECTION_INCONCLUSIVE',progression_authority=False),
            progression_authority=False)
        receipt=exporter.export({'mode':'startup-collection-failure'},[],attachments={
            'transport-capture.json':canonical(bundle)})
        path=Path(receipt['path'])
        if not verify_export(path)['valid']:raise ValueError('Failure export verification failed')
        replay=replay_transport_export(path.parent,path.name)
        return dict(export_path=str(path),export_verified=True,replay_verified=replay['matches'],
            summary=bundle['summary'],progression_authority=False)
    responses=[dict(path=item['path'],sha256=item['sha256'],
                    base64=base64.b64encode(item['raw']).decode('ascii'))
               for item in snapshot['responses']]
    bundle=dict(schema='rocell.transport_export.v1',responses=responses,
                summary=_summary(snapshot),progression_authority=False)
    if startup:bundle.update(schema='rocell.transport_export.v2',mode='startup')
    receipt=exporter.export({'mode':'read-only-diagnostic-transport'},[],attachments={
        'transport-capture.json':canonical(bundle)})
    path=Path(receipt['path'])
    if not verify_export(path)['valid']:
        raise ValueError('Transport export verification failed')
    replay=replay_transport_export(path.parent,path.name)
    return dict(export_path=str(path),export_verified=True,replay_verified=replay['matches'],
                summary=_summary(snapshot),progression_authority=False)


def replay_transport_export(root, export_id):
    bundle,_=_read(Path(root).resolve(),export_id,'attachment-transport-capture.json')
    return replay_transport_bundle(bundle)


def replay_transport_bundle(bundle):
    """Pure replay also validates internally consistent, rehashed malformed files."""
    if type(bundle) is dict and bundle.get('schema')=='rocell.startup_transport_failure.v1':
        return _replay_startup_failure(bundle)
    startup=type(bundle) is dict and bundle.get('schema')=='rocell.transport_export.v2'
    fields={'schema','responses','summary','progression_authority'}
    if startup:fields.add('mode')
    if (type(bundle) is not dict or set(bundle)!=fields
            or bundle['schema'] not in ('rocell.transport_export.v1','rocell.transport_export.v2')
            or (startup and bundle['mode']!='startup')
            or bundle['progression_authority'] is not False
            or type(bundle['responses']) is not list or not 2<=len(bundle['responses'])<=18):
        raise ValueError('Invalid transport export envelope')
    cursor=0

    def replay_get(path,*,maximum_bytes,timeout_seconds):
        nonlocal cursor
        if cursor>=len(bundle['responses']):raise ValueError('Missing retained response')
        item=bundle['responses'][cursor];cursor+=1
        if (type(item) is not dict or set(item)!={'path','sha256','base64'} or item['path']!=path
                or type(item['base64']) is not str
                or len(item['base64'])>4*((maximum_bytes+2)//3)):
            raise ValueError('Invalid retained response')
        try:raw=base64.b64decode(item['base64'],validate=True)
        except (ValueError,UnicodeError):raise ValueError('Invalid response encoding') from None
        if hashlib.sha256(raw).hexdigest()!=item['sha256']:
            raise ValueError('Retained response hash mismatch')
        return raw

    snapshot=collect_snapshot(replay_get,startup=startup)
    if cursor!=len(bundle['responses']) or canonical(_summary(snapshot))!=canonical(bundle['summary']):
        raise ValueError('Retained collection summary mismatch')
    return dict(matches=True,summary=_summary(snapshot),progression_authority=False)


def _replay_startup_failure(bundle):
    expected=dict(status='COLLECTION_INCONCLUSIVE',progression_authority=False)
    if (set(bundle)!={'schema','responses','summary','progression_authority'} or
            bundle['progression_authority'] is not False or canonical(bundle['summary'])!=canonical(expected) or
            type(bundle['responses']) is not list or not 1<=len(bundle['responses'])<=18):
        raise ValueError('Invalid startup failure envelope')
    cursor=0;invalid=False
    def get(path,*,maximum_bytes,timeout_seconds):
        nonlocal cursor,invalid
        if cursor>=len(bundle['responses']):
            invalid=True;raise ValueError('Missing retained failure response')
        item=bundle['responses'][cursor];cursor+=1
        if type(item) is not dict or item.get('path')!=path:
            invalid=True;raise ValueError('Failure response order mismatch')
        if set(item)=={'path','error'} and item['error'] in ('RECEIVE_FAILED','INVALID_RESPONSE_SIZE_OR_TYPE'):
            raise ValueError('Recorded receive failure')
        if (set(item)!={'path','sha256','base64'} or type(item['base64']) is not str or
                len(item['base64'])>4*((maximum_bytes+2)//3)):
            invalid=True;raise ValueError('Invalid retained failure body')
        try:raw=base64.b64decode(item['base64'],validate=True)
        except (ValueError,UnicodeError):
            invalid=True;raise ValueError('Invalid retained encoding') from None
        if not raw or len(raw)>maximum_bytes or hashlib.sha256(raw).hexdigest()!=item['sha256']:
            invalid=True;raise ValueError('Failure response identity mismatch')
        return raw
    failed=False
    try:collect_snapshot(get,startup=True)
    except (ValueError,KeyError,TypeError,OverflowError,RecursionError):failed=True
    if invalid or not failed or cursor!=len(bundle['responses']):
        raise ValueError('Recorded startup failure did not replay')
    return dict(matches=True,summary=expected,progression_authority=False)
