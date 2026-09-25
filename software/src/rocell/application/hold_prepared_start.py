"""Explicit hold send workflow; constructing objects has no device effect.

Caller must separately establish approved deployment/provisioning/servo admission.
No CLI or wizard action exposes this path yet. Injected senders may have effects.
"""
import hashlib
import json
from pathlib import Path

from .first_motion_contract import canonical
from .hold_command_contract import validate_hold_plan, sign_hold
from .hold_bound_replay import _policy
from .physical_onboarding_durability import publish_reservation_bytes
from .product_ghost_export_review import _read
from .servo_diagnostic_start_http import DiagnosticStartSender, DiagnosticStartError
from .wizard_diagnostic_export import WizardDiagnosticExporter, verify_export


class HoldStartSender(DiagnosticStartSender):
    delivery_schema = 'rocell.host_hold_delivery.v1'

    def __init__(self, address, port, approved_policy):
        _policy(approved_policy)
        self._policy = json.loads(canonical(approved_policy))
        super().__init__(address, port)

    def _prepare_request(self, plan, challenge, key):
        doc = validate_hold_plan(plan, boot_id=challenge['boot_id'], approved_policy=self._policy)
        return sign_hold(plan, challenge, key, approved_policy=self._policy), dict(
            hold_plan_sha256=hashlib.sha256(plan.encoded).hexdigest(),
            policy_sha256=doc['policy_sha256'], boot_id=doc['boot_id'], command_id=doc['command_id'])


def send_prepared_hold(root, sender, plan, challenge, key, *, approved_policy):
    """Export expectations and reserve shared nonce before exactly one send call.

    Lost replies, adapter exceptions and failed exports never refund the claim.
    Request acceptance is not servo dispatch or verified hold.
    """
    policy = json.loads(canonical(approved_policy))
    challenge = json.loads(canonical(challenge))
    document = validate_hold_plan(plan, boot_id=challenge['boot_id'], approved_policy=policy)
    sign_hold(plan, challenge, key, approved_policy=policy)
    root = Path(root).resolve()
    exporter = WizardDiagnosticExporter(root)
    exporter.prepare(create=True)
    attachments = {'hold-plan.json': plan.encoded, 'hold-policy.json': plan.policy_encoded,
                   'start-challenge.json': canonical(challenge)}
    preview = exporter.export({'mode': 'hold-pre-send'}, [], attachments=attachments)
    preview_path = Path(preview['path'])
    if not verify_export(preview_path)['valid']:
        raise ValueError('Hold preparation export invalid')
    for name, expected in attachments.items():
        retained, _ = _read(root, preview_path.name, 'attachment-' + name)
        if canonical(retained) != expected:
            raise ValueError('Hold preparation changed during export')
    plan_hash = hashlib.sha256(plan.encoded).hexdigest()
    identity = canonical(dict(boot_id=challenge['boot_id'], nonce=challenge['nonce']))
    claim_name = 'diagnostic-start-' + hashlib.sha256(identity).hexdigest() + '.json'
    claim = dict(schema='rocell.host_hold_claim.v1', plan_export_id=preview_path.name,
                 hold_plan_sha256=plan_hash, policy_sha256=document['policy_sha256'],
                 challenge_sha256=hashlib.sha256(canonical(challenge)).hexdigest(),
                 state='CONSUMED_BEFORE_SEND', retry_allowed=False)
    publish_reservation_bytes(root, claim_name, canonical(claim), maximum_bytes=2048)
    try:
        delivery = sender.send(plan, challenge, key)
    except DiagnosticStartError as error:
        delivery = error.report
    except Exception:
        # Do not leak arbitrary adapter exception text or treat a lost reply as
        # proof that the device received nothing. The claim remains consumed.
        delivery = dict(schema='rocell.host_hold_delivery.v1', result='DELIVERY_UNCERTAIN',
                        reason='ADAPTER_EXCEPTION', retry_allowed=False,
                        endpoint_verified=False, progression_authority=False)
    report = dict(schema='rocell.prepared_hold_result.v1', claim_file=claim_name,
                  plan_export_id=preview_path.name, hold_plan_sha256=plan_hash,
                  policy_sha256=document['policy_sha256'], delivery=delivery,
                  retry_allowed=False, progression_authority=False)
    exported = exporter.export({'mode': 'hold-delivery'}, [],
        attachments={'prepared-hold.json': canonical(report)})
    path = Path(exported['path'])
    if not verify_export(path)['valid']:
        raise ValueError('Hold delivery export failed; do not resend')
    retained, _ = _read(root, path.name, 'attachment-prepared-hold.json')
    if canonical(retained) != canonical(report):
        raise ValueError('Hold delivery export identity mismatch; do not resend')
    return dict(report, export_path=str(path), export_verified=True)
