"""One-use initial-pair token release from saved preparation; no transport.

Caller separately verifies installed capability and live-trial authorization.
No CLI/wizard route loads a key or exposes this operation yet.
"""
from dataclasses import dataclass, field
import hashlib
from pathlib import Path
from .first_motion_contract import canonical
from .held_pair_command_contract import HeldPairPlan, sign_held_pair
from .held_pair_preparation import replay_held_pair_preparation
from .physical_onboarding_durability import publish_reservation_bytes, read_bounded_regular_file
from .product_ghost_export_review import _read
from .wizard_diagnostic_export import WizardDiagnosticExporter
from .wizard_diagnostic_coordinator import decode_diagnostic_json
from .servo_start_authorization import _challenge_bytes


@dataclass(frozen=True)
class PreparedPairAuthorization:
    token: bytes = field(repr=False)
    context_export_id: str
    claim_file: str
    session_sha256: str


def replay_initial_pair_authorization(root, context_export_id):
    """Check saved preparation and consumed nonce without signing or sending.

    This proves local context consistency, not token delivery, device identity,
    or current challenge validity. A consumed claim is never refunded by replay.
    """
    root = Path(root).resolve()
    context, digest = _read(root, context_export_id,
                            'attachment-held-pair-signing-context.json')
    if (type(context) is not dict or set(context) != {
            'schema', 'preparation_export_id', 'preparation_sha256',
            'session_sha256', 'challenge', 'delivery_attempted', 'retry_allowed'} or
            context['schema'] != 'rocell.held_pair_signing_context.v1' or
            context['delivery_attempted'] is not False or
            context['retry_allowed'] is not False):
        raise ValueError('Invalid pair signing context')
    replay = replay_held_pair_preparation(root, context['preparation_export_id'])
    prepared = replay['preparation']
    challenge = context['challenge']
    _challenge_bytes(challenge)
    if (context['preparation_sha256'] != replay['preparation_sha256'] or
            context['session_sha256'] != prepared['pair_plan_sha256'] or
            challenge['boot_id'] != prepared['pair_plan']['boot_id']):
        raise ValueError('Pair signing source identity mismatch')
    identity = canonical(dict(boot_id=challenge['boot_id'], nonce=challenge['nonce']))
    claim_name = 'diagnostic-start-' + hashlib.sha256(identity).hexdigest() + '.json'
    expected = canonical(dict(schema='rocell.host_pair_claim.v1',
        context_export_id=context_export_id, context_sha256=digest,
        session_sha256=context['session_sha256'],
        state='CONSUMED_BEFORE_TOKEN_RELEASE', retry_allowed=False))
    if read_bounded_regular_file(root / claim_name, maximum_bytes=2048) != expected:
        raise ValueError('Pair nonce claim does not match saved context')
    return dict(replay_verified=True, context=context, context_sha256=digest,
                preparation=prepared, progression_authority=False,
                delivery_verified=False, provenance_verified=False)


def authorize_prepared_held_pair(root, preparation_export_id, challenge, key):
    """Export and verify context, then atomically consume nonce before return.

    A released token may be sent only once. Any subsequent failure does not
    refund the claim. This function itself never sends or retries anything.
    """
    root=Path(root).resolve()
    replay=replay_held_pair_preparation(root,preparation_export_id)
    prepared=replay['preparation']
    plan=HeldPairPlan(canonical(prepared['pair_plan']),canonical(prepared['policy']))
    # Freeze caller-owned challenge input before using it more than once.
    challenge=decode_diagnostic_json(canonical(challenge),maximum=1024)
    token=sign_held_pair(plan,challenge,key,approved_policy=prepared['policy'],
                        expected_hold_plan_sha256=prepared['pair_plan']['hold_plan_sha256'])
    context=dict(schema='rocell.held_pair_signing_context.v1',
        preparation_export_id=preparation_export_id,preparation_sha256=replay['preparation_sha256'],
        session_sha256=prepared['pair_plan_sha256'],challenge=challenge,
        delivery_attempted=False,retry_allowed=False)
    exporter=WizardDiagnosticExporter(root);exporter.prepare(create=True)
    saved=exporter.export({'mode':'held-pair-pre-authorization'},[],
                         attachments={'held-pair-signing-context.json':canonical(context)})
    context_id=Path(saved['path']).name
    retained,context_hash=_read(root,context_id,'attachment-held-pair-signing-context.json')
    if canonical(retained)!=canonical(context):
        raise ValueError('Pair signing context changed during export')
    identity=canonical(dict(boot_id=challenge['boot_id'],nonce=challenge['nonce']))
    # Same namespace as hold/start: a nonce cannot be reused across operation types.
    claim_name='diagnostic-start-'+hashlib.sha256(identity).hexdigest()+'.json'
    claim=canonical(dict(schema='rocell.host_pair_claim.v1',context_export_id=context_id,
        context_sha256=context_hash,session_sha256=context['session_sha256'],
        state='CONSUMED_BEFORE_TOKEN_RELEASE',retry_allowed=False))
    publish_reservation_bytes(root,claim_name,claim,maximum_bytes=2048)
    if read_bounded_regular_file(root/claim_name,maximum_bytes=2048)!=claim:
        raise ValueError('Pair nonce claim changed; do not retry')
    return PreparedPairAuthorization(token,context_id,claim_name,context['session_sha256'])
