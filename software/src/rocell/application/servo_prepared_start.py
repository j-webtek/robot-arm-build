"""Save/verify a plan and consume a durable claim before an injected one-use send.

No sender, socket or device is constructed here. This is not deployment admission.
Claims are never removed automatically, including after failed or uncertain sends.
"""
import hashlib
import json
from pathlib import Path

from .first_motion_contract import canonical
from .servo_start_authorization import sign_start
from .servo_diagnostic_start_http import DiagnosticStartError
from .wizard_diagnostic_export import WizardDiagnosticExporter, verify_export
from .physical_onboarding_durability import publish_reservation_bytes
from .product_ghost_export_review import _read


def send_prepared_start(root, sender, plan, challenge, key):
    document=plan.to_dict()
    if document.get('schema')!='rocell.session_plan.v3' or document.get('origin')!='DEVICE_CAPTURE':
        raise ValueError('Native whole-arm plan required')
    frozen_challenge=json.loads(canonical(challenge))
    # Validate the exact challenge/key/plan before touching storage or networking.
    # Signed bytes are deliberately not retained or exported.
    sign_start(plan,frozen_challenge,key)
    root=Path(root).resolve()
    exporter=WizardDiagnosticExporter(root);exporter.prepare(create=True)
    pre=exporter.export({'mode':'diagnostic-pre-send'},[],attachments={
        'session-plan.json':plan.encoded,'start-challenge.json':canonical(frozen_challenge)})
    pre_path=Path(pre['path'])
    if not verify_export(pre_path)['valid']:raise ValueError('Pre-send export verification failed')
    retained,_=_read(root,pre_path.name,'attachment-session-plan.json')
    retained_challenge,_=_read(root,pre_path.name,'attachment-start-challenge.json')
    if canonical(retained)!=plan.encoded or canonical(retained_challenge)!=canonical(frozen_challenge):
        raise ValueError('Pre-send records differ from frozen request')

    # Boot+nonce identifies the attempt, regardless of plan/command/expiry changes.
    # CREATE_NEW is the cross-process arbiter; even an incomplete file consumes it.
    identity=canonical(dict(boot_id=frozen_challenge['boot_id'],nonce=frozen_challenge['nonce']))
    claim_name='diagnostic-start-'+hashlib.sha256(identity).hexdigest()+'.json'
    claim=dict(schema='rocell.host_start_claim.v1',plan_export_id=pre_path.name,
        session_plan_sha256=plan.sha256,challenge_sha256=hashlib.sha256(canonical(frozen_challenge)).hexdigest(),
        state='CONSUMED_BEFORE_SEND',retry_allowed=False)
    publish_reservation_bytes(root,claim_name,canonical(claim),maximum_bytes=2048)
    try:
        delivery=sender.send(plan,frozen_challenge,key)
    except DiagnosticStartError as error:
        delivery=error.report
    report=dict(schema='rocell.prepared_start_result.v1',claim_file=claim_name,
        plan_export_id=pre_path.name,session_plan_sha256=plan.sha256,delivery=delivery,
        retry_allowed=False,progression_authority=False)
    post=exporter.export({'mode':'diagnostic-start-delivery'},[],attachments={
        'prepared-start.json':canonical(report)})
    post_path=Path(post['path'])
    if not verify_export(post_path)['valid']:raise ValueError('Delivery export verification failed; do not resend')
    retained,_=_read(root,post_path.name,'attachment-prepared-start.json')
    if canonical(retained)!=canonical(report):raise ValueError('Delivery export differs; do not resend')
    return dict(report,export_path=str(post_path),export_verified=True)
