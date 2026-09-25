"""Explicit recovery preparation/signing. No automatic calls or hardware CLI.

The caller must establish approved installation and one-shot recovery authority.
The injected sender may have physical effects. No key/token is retained in exports.
"""
from dataclasses import dataclass
import hashlib
import hmac
import struct
from pathlib import Path

from .first_motion_contract import canonical
from .physical_onboarding_durability import publish_reservation_bytes
from .servo_diagnostic_contract import _identifier
from .servo_diagnostic_start_http import DiagnosticStartSender, DiagnosticStartError
from .servo_start_authorization import DOMAIN, _challenge_bytes, _hex, _key
from .supported_recovery_review import recovery_policy
from .wizard_diagnostic_coordinator import decode_diagnostic_json
from .wizard_diagnostic_export import WizardDiagnosticExporter, verify_export


@dataclass(frozen=True)
class RecoveryPlan:
    encoded: bytes
    policy_encoded: bytes


def freeze_recovery_plan(policy, *, boot_id, command_id, profile='supported'):
    recovery_policy(policy,profile=profile)
    _hex(boot_id, 16)
    _identifier(command_id)
    policy_bytes = canonical(policy)
    return RecoveryPlan(canonical(dict(schema=f'rocell.{profile}_recovery_plan.v1',
        boot_id=boot_id, command_id=command_id, origin='DEVICE_CAPTURE',
        policy_sha256=hashlib.sha256(policy_bytes).hexdigest())), policy_bytes)


def validate_recovery_plan(plan, *, boot_id, approved_policy, profile='supported'):
    if type(plan) is not RecoveryPlan or type(plan.encoded) is not bytes or type(plan.policy_encoded) is not bytes:
        raise ValueError('Frozen recovery plan required')
    doc = decode_diagnostic_json(plan.encoded, maximum=1536)
    expected = freeze_recovery_plan(approved_policy, boot_id=boot_id, command_id=doc['command_id'],profile=profile)
    if plan != expected:
        raise ValueError('Recovery plan/policy/boot mismatch')
    return doc


def sign_recovery(plan, challenge, key, *, approved_policy, profile='supported'):
    _key(key)
    header = _challenge_bytes(challenge)
    validate_recovery_plan(plan, boot_id=challenge['boot_id'], approved_policy=approved_policy,profile=profile)
    body = DOMAIN + header + struct.pack('>H', len(plan.encoded)) + plan.encoded
    return body + hmac.digest(key, body, 'sha256')


class RecoveryStartSender(DiagnosticStartSender):
    delivery_schema = 'rocell.host_recovery_delivery.v1'

    def __init__(self, address, port, approved_policy, *, profile='supported'):
        recovery_policy(approved_policy,profile=profile)
        self._profile=profile
        self._policy = decode_diagnostic_json(canonical(approved_policy), maximum=2048)
        super().__init__(address, port)

    def _prepare_request(self, plan, challenge, key):
        doc = validate_recovery_plan(plan, boot_id=challenge['boot_id'], approved_policy=self._policy,profile=self._profile)
        return sign_recovery(plan, challenge, key, approved_policy=self._policy,profile=self._profile), dict(
            recovery_plan_sha256=hashlib.sha256(plan.encoded).hexdigest(),
            policy_sha256=doc['policy_sha256'], boot_id=doc['boot_id'], command_id=doc['command_id'])


def send_prepared_recovery(root, sender, plan, challenge, key, *, approved_policy, profile='supported'):
    """Persist expectations and a shared nonce claim before exactly one send.

    A failed response/export never refunds the claim. Acceptance is not arrival.
    """
    challenge = decode_diagnostic_json(canonical(challenge), maximum=2048)
    doc = validate_recovery_plan(plan, boot_id=challenge['boot_id'], approved_policy=approved_policy,profile=profile)
    sign_recovery(plan, challenge, key, approved_policy=approved_policy,profile=profile)
    root = Path(root).resolve()
    exporter = WizardDiagnosticExporter(root)
    exporter.prepare(create=True)

    def retain(mode, attachments):
        exported = exporter.export({'mode': mode}, [], attachments=attachments)
        path = Path(exported['path'])
        if not verify_export(path)['valid']:
            raise ValueError('Recovery export invalid; do not resend')
        for name, expected in attachments.items():
            retained = decode_diagnostic_json((path / ('attachment-' + name)).read_bytes(), maximum=60000)
            if canonical(retained) != expected:
                raise ValueError('Recovery export changed; do not resend')
        return path

    preview = retain('recovery-pre-send', {'recovery-plan.json': plan.encoded,
        'recovery-policy.json': plan.policy_encoded, 'start-challenge.json': canonical(challenge)})
    plan_hash = hashlib.sha256(plan.encoded).hexdigest()
    # Shared with ordinary hold/diagnostics, so the same nonce cannot be reused
    # through a different host entry point after uncertain delivery.
    identity = canonical(dict(boot_id=challenge['boot_id'], nonce=challenge['nonce']))
    claim_name = 'diagnostic-start-' + hashlib.sha256(identity).hexdigest() + '.json'
    claim = dict(schema='rocell.host_recovery_claim.v1', plan_export_id=preview.name,
        recovery_plan_sha256=plan_hash, policy_sha256=doc['policy_sha256'],
        challenge_sha256=hashlib.sha256(canonical(challenge)).hexdigest(),
        state='CONSUMED_BEFORE_SEND', retry_allowed=False)
    publish_reservation_bytes(root, claim_name, canonical(claim), maximum_bytes=2048)
    try:
        delivery = sender.send(plan, challenge, key)
    except DiagnosticStartError as error:
        delivery = error.report
    except Exception:
        delivery = dict(schema='rocell.host_recovery_delivery.v1', result='DELIVERY_UNCERTAIN',
            reason='ADAPTER_EXCEPTION', retry_allowed=False, endpoint_verified=False,
            progression_authority=False)
    report = dict(schema='rocell.prepared_recovery_result.v1', claim_file=claim_name,
        plan_export_id=preview.name, recovery_plan_sha256=plan_hash,
        policy_sha256=doc['policy_sha256'], delivery=delivery,
        retry_allowed=False, progression_authority=False)
    path = retain('recovery-delivery', {'prepared-recovery.json': canonical(report)})
    return dict(report, export_path=str(path), export_verified=True)
