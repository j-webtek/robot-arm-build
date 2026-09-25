"""Explicit startup send preparation; not installed capability or motion approval.

The caller must establish reviewed firmware, provisioning and physical admission.
Construction is inert. Tokens/keys never enter diagnostic exports.
"""
import hashlib
import json
from pathlib import Path

from .first_motion_contract import canonical
from .servo_diagnostic_start_http import DiagnosticStartSender, DiagnosticStartError
from .startup_command_contract import validate_startup_policy, validate_startup_plan, sign_startup
from .wizard_diagnostic_export import WizardDiagnosticExporter, verify_export
from .physical_onboarding_durability import publish_reservation_bytes
from .product_ghost_export_review import _read


class StartupStartSender(DiagnosticStartSender):
    delivery_schema = 'rocell.host_startup_delivery.v1'

    def __init__(self, address, port, approved_policy):
        validate_startup_policy(approved_policy)
        self._policy = json.loads(canonical(approved_policy))
        super().__init__(address, port)

    def _prepare_request(self, plan, challenge, key):
        doc = validate_startup_plan(plan, challenge['boot_id'], self._policy)
        if doc['origin'] != 'DEVICE_CAPTURE':
            raise ValueError('Native startup plan required')
        return sign_startup(plan, challenge, key, self._policy), dict(
            startup_plan_sha256=hashlib.sha256(plan.encoded).hexdigest(),
            boot_id=doc['command']['boot_id'], command_id=doc['command']['command_id'])


def send_prepared_startup(root, sender, plan, challenge, key, *, approved_policy):
    """Persist exact expectations and consume a shared boot/nonce claim first.

    No adapter is constructed here; the injected sender may have live effects.
    Failed/uncertain sends and export failures never release the claim.
    """
    policy = json.loads(canonical(approved_policy))
    challenge = json.loads(canonical(challenge))
    doc = validate_startup_plan(plan, challenge['boot_id'], policy)
    if doc['origin'] != 'DEVICE_CAPTURE':raise ValueError('Native startup plan required')
    sign_startup(plan, challenge, key, policy)  # Validate; do not retain signed bytes.
    digest = hashlib.sha256(plan.encoded).hexdigest()
    root = Path(root).resolve()
    exporter = WizardDiagnosticExporter(root); exporter.prepare(create=True)
    context = dict(boot_id=challenge['boot_id'], approved_policy=policy)
    pre = exporter.export({'mode': 'startup-pre-send'}, [], attachments={
        'startup-plan.json': plan.encoded, 'startup-context.json': canonical(context),
        'start-challenge.json': canonical(challenge)})
    pre_path = Path(pre['path'])
    if not verify_export(pre_path)['valid']:raise ValueError('Startup pre-send export failed')
    for name, expected in (('startup-plan', plan.encoded), ('startup-context', canonical(context)),
                           ('start-challenge', canonical(challenge))):
        retained, _ = _read(root, pre_path.name, 'attachment-' + name + '.json')
        if canonical(retained) != expected:raise ValueError('Startup pre-send identity mismatch')
    identity = canonical(dict(boot_id=challenge['boot_id'], nonce=challenge['nonce']))
    # Same namespace as normal starts prevents mode changes from bypassing a claim.
    claim_name = 'diagnostic-start-' + hashlib.sha256(identity).hexdigest() + '.json'
    claim = dict(schema='rocell.host_startup_claim.v1', plan_export_id=pre_path.name,
        startup_plan_sha256=digest, challenge_sha256=hashlib.sha256(canonical(challenge)).hexdigest(),
        state='CONSUMED_BEFORE_SEND', retry_allowed=False)
    publish_reservation_bytes(root, claim_name, canonical(claim), maximum_bytes=2048)
    try:
        delivery = sender.send(plan, challenge, key)
    except DiagnosticStartError as error:
        delivery = error.report
    report = dict(schema='rocell.prepared_startup_result.v1', claim_file=claim_name,
        plan_export_id=pre_path.name, startup_plan_sha256=digest, delivery=delivery,
        retry_allowed=False, progression_authority=False)
    post = exporter.export({'mode': 'startup-delivery'}, [],
        attachments={'prepared-startup.json': canonical(report)})
    path = Path(post['path'])
    if not verify_export(path)['valid']:raise ValueError('Startup delivery export failed; do not resend')
    retained, _ = _read(root, path.name, 'attachment-prepared-startup.json')
    if canonical(retained) != canonical(report):raise ValueError('Startup delivery identity mismatch')
    return dict(report, export_path=str(path), export_verified=True)
