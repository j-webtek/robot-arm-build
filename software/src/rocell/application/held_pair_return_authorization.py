"""One-use return token from reopened forward evidence; no transport or key load.

The caller must separately establish installed capability and live admission.
The controller independently checks its retained forward evidence and freshly
samples before moving. This host archive alone cannot establish current posture.
"""
import hashlib
import hmac
import struct
from pathlib import Path

from .first_motion_contract import canonical
from .held_pair_observed_forward import replay_observed_pair_forward
from .held_pair_prepared_authorization import PreparedPairAuthorization
from .physical_onboarding_durability import publish_reservation_bytes, read_bounded_regular_file
from .product_ghost_export_review import _read
from .servo_start_authorization import DOMAIN, _challenge_bytes, _hex, _key
from .wizard_diagnostic_coordinator import decode_diagnostic_json
from .wizard_diagnostic_export import WizardDiagnosticExporter


def _context(root, forward_export_id, challenge, forward_delivery_export_id):
    """Derive all signed fields from replay, never from caller-supplied targets."""
    challenge = decode_diagnostic_json(canonical(challenge), maximum=1024)
    _challenge_bytes(challenge)
    replay = replay_observed_pair_forward(root, forward_export_id)
    assessment = replay['assessment']
    if (assessment.get('category') != 'CONTROLLER_REPORTED_ARRIVAL' or
            assessment.get('stable_status_observed') is not True or
            assessment.get('historical_anchor_matches') is not True or
            assessment.get('controller_state') != 'AWAITING_EXPORT'):
        raise ValueError('Return requires stable arrived forward evidence at the original anchor')
    source = replay['authorization']
    # Import lazily: delivery also uses return-context replay. Restrict to the
    # forward leg before source traversal to prevent recursive return links.
    from .held_pair_delivery import replay_pair_delivery
    delivery_replay = replay_pair_delivery(root, forward_delivery_export_id, expected_leg='forward')
    delivery = delivery_replay['report']['delivery']
    if (delivery['result'] != 'CONTROLLER_REPORTED_ACCEPTANCE' or
            delivery['context_sha256'] != source['context_sha256'] or
            delivery['session_sha256'] != source['preparation']['pair_plan_sha256'] or
            delivery['boot_id'] != source['preparation']['pair_plan']['boot_id']):
        raise ValueError('Return requires accepted delivery for the same forward authorization')
    prepared = source['preparation']
    pair = prepared['pair_plan']
    initial_challenge = source['context']['challenge']
    if (challenge['boot_id'] != pair['boot_id'] or
            challenge['nonce'] == initial_challenge['nonce'] or
            challenge['issued_us'] <= initial_challenge['issued_us']):
        raise ValueError('Return requires a distinct later same-boot challenge')
    # These hashes describe exact retained bytes. They are not device attestations.
    _hex(assessment['evidence_sha256'], 32)
    _hex(replay['export_sha256'], 32)
    payload = dict(schema='rocell.held_return_authorization.v1', origin='DEVICE_CAPTURE',
        boot_id=pair['boot_id'], session_sha256=prepared['pair_plan_sha256'],
        forward_plan_sha256=hashlib.sha256(canonical(replay['forward_plan'])).hexdigest(),
        evidence_sha256=assessment['evidence_sha256'], export_sha256=replay['export_sha256'],
        return_target_count=prepared['historical_anchor'])
    return dict(schema='rocell.held_return_signing_context.v2', forward_export_id=forward_export_id,
                forward_delivery_export_id=forward_delivery_export_id,
                forward_delivery_sha256=delivery_replay['export_sha256'],
                challenge=challenge, payload=payload, delivery_attempted=False, retry_allowed=False)


def _claim(context_id, context_hash, context):
    challenge = context['challenge']
    identity = canonical(dict(boot_id=challenge['boot_id'], nonce=challenge['nonce']))
    name = 'diagnostic-start-' + hashlib.sha256(identity).hexdigest() + '.json'
    data = canonical(dict(schema='rocell.host_pair_return_claim.v1',
        context_export_id=context_id, context_sha256=context_hash,
        session_sha256=context['payload']['session_sha256'],
        state='CONSUMED_BEFORE_TOKEN_RELEASE', retry_allowed=False))
    return name, data


def authorize_observed_pair_return(root, forward_export_id, challenge, key, *, forward_delivery_export_id):
    """Export/reopen context and consume nonce before releasing one token.

    No failure refunds a consumed claim. Tokens are memory-only and excluded
    from result repr; neither keys nor tokens are placed in diagnostic exports.
    """
    root = Path(root).resolve()
    _key(key)
    context = _context(root, forward_export_id, challenge, forward_delivery_export_id)
    payload = canonical(context['payload'])
    unsigned = DOMAIN + _challenge_bytes(context['challenge']) + struct.pack('>H', len(payload)) + payload
    token = unsigned + hmac.digest(key, unsigned, 'sha256')
    exporter = WizardDiagnosticExporter(root)
    exporter.prepare(create=True)
    saved = exporter.export({'mode': 'held-return-pre-authorization'}, [],
        attachments={'held-return-signing-context.json': canonical(context)})
    context_id = Path(saved['path']).name
    retained, digest = _read(root, context_id, 'attachment-held-return-signing-context.json')
    if canonical(retained) != canonical(context):
        raise ValueError('Return signing context changed during export')
    # Reopen and reassess the forward chain before making token release durable.
    if canonical(_context(root, forward_export_id, context['challenge'], forward_delivery_export_id)) != canonical(context):
        raise ValueError('Forward evidence changed before return authorization')
    name, data = _claim(context_id, digest, context)
    publish_reservation_bytes(root, name, data, maximum_bytes=2048)
    if read_bounded_regular_file(root / name, maximum_bytes=2048) != data:
        raise ValueError('Return nonce claim changed; do not retry')
    return PreparedPairAuthorization(token, context_id, name, context['payload']['session_sha256'])


def replay_pair_return_authorization(root, context_export_id):
    """Validate saved return context and claim; does not prove token delivery."""
    root = Path(root).resolve()
    context, digest = _read(root, context_export_id, 'attachment-held-return-signing-context.json')
    if type(context) is not dict or not {'forward_export_id', 'challenge', 'forward_delivery_export_id'} <= context.keys():
        raise ValueError('Invalid return signing context')
    expected = _context(root, context['forward_export_id'], context['challenge'], context['forward_delivery_export_id'])
    if canonical(context) != canonical(expected):
        raise ValueError('Return context differs from replayed forward evidence')
    name, data = _claim(context_export_id, digest, context)
    if read_bounded_regular_file(root / name, maximum_bytes=2048) != data:
        raise ValueError('Return nonce claim mismatch')
    return dict(replay_verified=True, context=context, context_sha256=digest,
                delivery_verified=False, progression_authority=False, provenance_verified=False)
