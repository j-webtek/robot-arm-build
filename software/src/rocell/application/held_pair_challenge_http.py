"""Explicit state-changing challenge POSTs; no motion token, key load or retries.

Caller must verify installed capability and export hold/forward evidence first.
Prepare retires device hold evidence. Neither request is a read-only probe.
"""
import base64
import hashlib
import socket
import time
from pathlib import Path

from .first_motion_contract import canonical
from .physical_onboarding_durability import publish_reservation_bytes, read_bounded_regular_file
from .product_ghost_export_review import _read
from .servo_diagnostic_http import DiagnosticHTTPReader, _content_length
from .servo_start_authorization import _challenge_bytes, _hex
from .wizard_diagnostic_coordinator import decode_diagnostic_json
from .wizard_diagnostic_export import WizardDiagnosticExporter

ROUTES = {'prepare':'/rocell/held-pair/prepare', 'return':'/rocell/held-pair/return-challenge',
          'recovery':'/rocell/recovery/prepare'}


def request_recovery_challenge(root, *, expected_boot, address, port=80):
    """One explicit recovery prepare; uses the shared retained POST contract.

    Legacy receipt schema names are retained, but operation/path are bound to
    recovery and cannot be substituted for pair prepare or return admission.
    """
    return request_pair_challenge(root, operation='recovery', expected_boot=expected_boot,
                                  address=address, port=port)


def request_pair_challenge(root, *, operation, expected_boot, address, port=80):
    """Reserve one operation per boot before a single bounded POST attempt.

    Even a failed connection consumes this host attempt. Export failure after
    transmission never permits reissuing the request. No automatic progression.
    """
    if operation not in ROUTES:
        raise ValueError('Explicit prepare or return challenge required')
    _hex(expected_boot,16)
    checked = DiagnosticHTTPReader(address,port)  # Pure numeric-address validation.
    root = Path(root).resolve()
    exporter = WizardDiagnosticExporter(root)
    exporter.prepare(create=True)
    intent = dict(schema='rocell.pair_challenge_intent.v1', operation=operation,
                  expected_boot=expected_boot, address=checked.address, port=checked.port,
                  path=ROUTES[operation], retry_allowed=False)
    saved = exporter.export({'mode':'pair-challenge-intent'},[],
        attachments={'pair-challenge-intent.json':canonical(intent)})
    intent_id = Path(saved['path']).name
    retained, digest = _read(root,intent_id,'attachment-pair-challenge-intent.json')
    if canonical(retained) != canonical(intent):raise ValueError('Challenge intent changed')
    name, claim = _claim(intent,intent_id,digest)
    publish_reservation_bytes(root,name,claim,maximum_bytes=2048)
    if read_bounded_regular_file(root/name,maximum_bytes=2048) != claim:
        raise ValueError('Challenge claim readback failed; do not retry')
    result = dict(category='CHALLENGE_UNCERTAIN', connection_attempted=False,
                  transmission_attempted=False, response_base64='', challenge=None,
                  progression_authority=False, retry_allowed=False)
    deadline = time.monotonic()+3.0
    def remaining():
        value=deadline-time.monotonic()
        if value<=0:raise TimeoutError('Challenge deadline')
        return value
    try:
        with socket.socket(socket.AF_INET,socket.SOCK_STREAM) as connection:
            result['connection_attempted']=True
            connection.settimeout(remaining());connection.connect((checked.address,checked.port))
            request=(f'POST {intent["path"]} HTTP/1.1\r\nHost: {checked.address}:{checked.port}\r\n'
                     'Content-Length: 0\r\nConnection: close\r\n\r\n').encode('ascii')
            connection.settimeout(remaining());result['transmission_attempted']=True
            connection.sendall(request)
            def receive(n):
                connection.settimeout(remaining());data=connection.recv(n);remaining()
                if not data:raise ValueError('Truncated challenge reply')
                return data
            header=bytearray()
            while not header.endswith(b'\r\n\r\n'):
                if len(header)>=2048:raise ValueError('Challenge header budget')
                header.extend(receive(1))
            length=_content_length(bytes(header),512)
            raw=bytearray()
            while len(raw)<length:raw.extend(receive(length-len(raw)))
            result['response_base64']=base64.b64encode(raw).decode('ascii')
            challenge=decode_diagnostic_json(bytes(raw),maximum=512)
            _challenge_bytes(challenge)
            if challenge['boot_id']!=expected_boot:raise ValueError('Wrong challenge boot')
            result.update(category='CHALLENGE_RECEIVED',challenge=challenge)
    except (OSError,ValueError,TypeError,KeyError,UnicodeError):
        pass  # Do not expose exception text or infer that nothing reached device.
    report=dict(schema='rocell.pair_challenge_result.v1',intent_export_id=intent_id,
                intent_sha256=digest,result=result)
    saved=exporter.export({'mode':'pair-challenge-result'},[],
        attachments={'pair-challenge-result.json':canonical(report)})
    retained,_=_read(root,Path(saved['path']).name,'attachment-pair-challenge-result.json')
    if canonical(retained)!=canonical(report):raise ValueError('Challenge export changed; do not retry')
    replay_pair_challenge(root,Path(saved['path']).name)
    return dict(export_path=saved['path'],report=report,export_verified=True,progression_authority=False)


def _claim(intent,intent_id,digest):
    identity=canonical(dict(boot_id=intent['expected_boot'],operation=intent['operation']))
    name='pair-challenge-'+hashlib.sha256(identity).hexdigest()+'.json'
    claim=canonical(dict(schema='rocell.pair_challenge_claim.v1',intent_export_id=intent_id,
                         intent_sha256=digest,state='CONSUMED_BEFORE_POST',retry_allowed=False))
    return name,claim


def replay_pair_challenge(root, export_id):
    """Verify intent, claim and retained challenge bytes without opening sockets."""
    root=Path(root).resolve()
    report,digest=_read(root,export_id,'attachment-pair-challenge-result.json')
    if (type(report) is not dict or set(report)!={'schema','intent_export_id','intent_sha256','result'} or
            report['schema']!='rocell.pair_challenge_result.v1'):
        raise ValueError('Invalid challenge receipt')
    intent,intent_hash=_read(root,report['intent_export_id'],'attachment-pair-challenge-intent.json')
    if (type(intent) is not dict or set(intent)!={'schema','operation','expected_boot','address','port','path','retry_allowed'} or
            intent['schema']!='rocell.pair_challenge_intent.v1' or intent['operation'] not in ROUTES or
            intent['path']!=ROUTES[intent['operation']] or intent['retry_allowed'] is not False or
            intent_hash!=report['intent_sha256']):
        raise ValueError('Invalid challenge intent')
    _hex(intent['expected_boot'],16)
    DiagnosticHTTPReader(intent['address'],intent['port'])
    name,claim=_claim(intent,report['intent_export_id'],intent_hash)
    if read_bounded_regular_file(root/name,maximum_bytes=2048)!=claim:
        raise ValueError('Challenge claim mismatch')
    result=report['result']
    if (type(result) is not dict or set(result)!={'category','connection_attempted','transmission_attempted',
            'response_base64','challenge','progression_authority','retry_allowed'} or
            result['category'] not in ('CHALLENGE_RECEIVED','CHALLENGE_UNCERTAIN') or
            any(type(result[k]) is not bool for k in ('connection_attempted','transmission_attempted')) or
            result['progression_authority'] is not False or result['retry_allowed'] is not False or
            (result['transmission_attempted'] and not result['connection_attempted']) or
            type(result['response_base64']) is not str or len(result['response_base64'])>684):
        raise ValueError('Invalid challenge result')
    raw=base64.b64decode(result['response_base64'],validate=True)
    if len(raw)>512 or base64.b64encode(raw).decode('ascii')!=result['response_base64']:
        raise ValueError('Invalid challenge response bytes')
    if result['category']=='CHALLENGE_RECEIVED':
        parsed=decode_diagnostic_json(raw,maximum=512);_challenge_bytes(parsed)
        if (not result['transmission_attempted'] or parsed['boot_id']!=intent['expected_boot'] or
                canonical(parsed)!=canonical(result['challenge'])):
            raise ValueError('Challenge response mismatch')
    elif result['challenge'] is not None:
        raise ValueError('Uncertain receipt cannot supply a challenge')
    return dict(replay_verified=True,report=report,intent=intent,export_sha256=digest,
                progression_authority=False,provenance_verified=False)
