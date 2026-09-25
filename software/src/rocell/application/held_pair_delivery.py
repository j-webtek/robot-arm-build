"""Explicit one-shot pair POST with durable local claim; never retry or move on.

Caller must establish reviewed installed capability and live-trial admission.
No wizard/CLI exposes this helper yet. Acceptance is not motion or arrival.
"""
import hashlib
import struct
from pathlib import Path

from .first_motion_contract import canonical
from .held_pair_prepared_authorization import PreparedPairAuthorization, replay_initial_pair_authorization
from .held_pair_return_authorization import replay_pair_return_authorization
from .physical_onboarding_durability import publish_reservation_bytes, read_bounded_regular_file
from .product_ghost_export_review import _read
from .servo_diagnostic_start_http import DiagnosticStartSender, DiagnosticStartError
from .servo_start_authorization import DOMAIN, _challenge_bytes
from .wizard_diagnostic_coordinator import decode_diagnostic_json
from .wizard_diagnostic_export import WizardDiagnosticExporter


def _source(root, context_id, leg):
    if leg == 'forward':
        source = replay_initial_pair_authorization(root, context_id)
        payload = source['preparation']['pair_plan']
        session = source['preparation']['pair_plan_sha256']
    elif leg == 'return':
        source = replay_pair_return_authorization(root, context_id)
        payload = source['context']['payload']
        session = payload['session_sha256']
    else:
        raise ValueError('Named forward or return leg required')
    challenge = source['context']['challenge']
    encoded = canonical(payload)
    unsigned = DOMAIN + _challenge_bytes(challenge) + struct.pack('>H', len(encoded)) + encoded
    identity = dict(boot_id=challenge['boot_id'], session_sha256=session, leg=leg,
                    context_export_id=context_id, context_sha256=source['context_sha256'])
    nonce_hash = hashlib.sha256(canonical(dict(boot_id=challenge['boot_id'],nonce=challenge['nonce']))).hexdigest()
    return unsigned, identity, 'diagnostic-delivery-' + nonce_hash + '.json'


class _PairSender(DiagnosticStartSender):
    delivery_schema = 'rocell.host_pair_delivery.v1'

    def _prepare_request(self, token, identity, unused):
        return token, identity


def send_authorized_pair(root, authorization, *, leg, address, port=8081):
    """One explicit send after source replay and atomic delivery reservation.

    Failure after claim consumption is terminal even if zero bytes were sent.
    Lost replies and report-export failures never permit another attempt.
    """
    root = Path(root).resolve()
    if type(authorization) is not PreparedPairAuthorization:
        raise ValueError('Released pair authorization required')
    unsigned, identity, claim_name = _source(root, authorization.context_export_id, leg)
    token = authorization.token
    if (type(token) is not bytes or len(token) != len(unsigned)+32 or
            token[:-32] != unsigned or authorization.session_sha256 != identity['session_sha256']):
        raise ValueError('Released token differs from saved authorization')
    # The host checks exact envelope binding; only the device authenticates its HMAC.
    sender = _PairSender(address, port)  # Address validation only; no connection.
    exporter = WizardDiagnosticExporter(root)
    exporter.prepare(create=True)
    intent = dict(schema='rocell.pair_delivery_intent.v1', **identity,
                  address=sender.address, port=sender.port, retry_allowed=False)
    saved = exporter.export({'mode':'pair-delivery-intent'}, [],
                            attachments={'pair-delivery-intent.json':canonical(intent)})
    intent_id = Path(saved['path']).name
    retained, digest = _read(root, intent_id, 'attachment-pair-delivery-intent.json')
    if canonical(retained) != canonical(intent):
        raise ValueError('Delivery intent changed during export')
    claim = canonical(dict(schema='rocell.pair_delivery_claim.v1', intent_export_id=intent_id,
                           intent_sha256=digest, state='CONSUMED_BEFORE_SEND', retry_allowed=False))
    publish_reservation_bytes(root, claim_name, claim, maximum_bytes=2048)
    if read_bounded_regular_file(root/claim_name, maximum_bytes=2048) != claim:
        raise ValueError('Delivery claim readback failed; do not resend')
    try:
        delivery = sender.send(token, identity, None)
    except DiagnosticStartError as exc:
        delivery = exc.report
    except Exception:
        # Never leak token-bearing adapter exceptions or infer no delivery.
        delivery = dict(schema='rocell.host_pair_delivery.v1', **identity,
                        result='DELIVERY_UNCERTAIN', retry_allowed=False,
                        progression_authority=False, endpoint_verified=False)
    report = dict(schema='rocell.pair_delivery_result.v1', intent_export_id=intent_id,
                  intent_sha256=digest, delivery=delivery, progression_authority=False,
                  retry_allowed=False)
    saved = exporter.export({'mode':'pair-delivery-result'}, [],
                            attachments={'pair-delivery-result.json':canonical(report)})
    replay = replay_pair_delivery(root, Path(saved['path']).name)
    return dict(export_path=saved['path'], **replay)


def replay_pair_delivery(root, export_id, *, expected_leg=None):
    """Check saved source/intent/claim/result without keys, signing or network."""
    root = Path(root).resolve()
    report, digest = _read(root, export_id, 'attachment-pair-delivery-result.json')
    if (type(report) is not dict or set(report) != {'schema','intent_export_id','intent_sha256',
            'delivery','progression_authority','retry_allowed'} or
            report['schema'] != 'rocell.pair_delivery_result.v1' or
            report['progression_authority'] is not False or report['retry_allowed'] is not False):
        raise ValueError('Invalid pair delivery report')
    intent, intent_hash = _read(root, report['intent_export_id'], 'attachment-pair-delivery-intent.json')
    if expected_leg is not None and intent.get('leg') != expected_leg:
        raise ValueError('Unexpected delivery leg')
    _, identity, claim_name = _source(root, intent['context_export_id'], intent['leg'])
    checked = _PairSender(intent['address'], intent['port'])
    expected = dict(schema='rocell.pair_delivery_intent.v1', **identity,
                    address=checked.address, port=checked.port, retry_allowed=False)
    if canonical(intent) != canonical(expected) or intent_hash != report['intent_sha256']:
        raise ValueError('Delivery intent/source mismatch')
    claim = canonical(dict(schema='rocell.pair_delivery_claim.v1', intent_export_id=report['intent_export_id'],
                           intent_sha256=intent_hash, state='CONSUMED_BEFORE_SEND', retry_allowed=False))
    if read_bounded_regular_file(root/claim_name, maximum_bytes=2048) != claim:
        raise ValueError('Delivery claim mismatch')
    delivery = report['delivery']
    if (type(delivery) is not dict or delivery.get('schema') != 'rocell.host_pair_delivery.v1' or
            any(delivery.get(k) != v for k,v in identity.items()) or
            any(delivery.get(k) is not False for k in ('retry_allowed','progression_authority','endpoint_verified')) or
            delivery.get('result') not in ('CONTROLLER_REPORTED_ACCEPTANCE','CONTROLLER_REPORTED_REJECTION',
                                          'DELIVERY_UNCERTAIN','CONNECTION_UNVERIFIED','PREPARATION_REJECTED')):
        raise ValueError('Invalid pair delivery assessment')
    result = delivery['result']
    if result in ('CONTROLLER_REPORTED_ACCEPTANCE','CONTROLLER_REPORTED_REJECTION'):
        raw = delivery['response_body'].encode('ascii')
        expected_body = dict(accepted=result=='CONTROLLER_REPORTED_ACCEPTANCE', retry_allowed=False)
        if (canonical(decode_diagnostic_json(raw, maximum=256)) != canonical(expected_body) or
                hashlib.sha256(raw).hexdigest() != delivery['response_sha256'] or
                delivery.get('connection_attempted') is not True or
                delivery.get('transmission_attempted') is not True):
            raise ValueError('Delivery response contradicts result')
    return dict(replay_verified=True, report=report, export_sha256=digest,
                progression_authority=False, endpoint_verified=False, provenance_verified=False)
