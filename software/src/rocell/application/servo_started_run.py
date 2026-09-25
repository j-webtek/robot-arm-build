"""Link a consumed host attempt to later read-only capture and replay. Never send."""
import base64
import hashlib
from pathlib import Path

from .first_motion_contract import canonical
from .product_ghost_export_review import _read
from .physical_onboarding_durability import contained_path,read_bounded_regular_file
from .servo_session_plan import SessionPlan
from .servo_start_authorization import _challenge_bytes
from .servo_planned_run import collect_planned_run,replay_planned_run
from .wizard_diagnostic_export import WizardDiagnosticExporter,verify_export


def _prepared(root,export_id):
    report,digest=_read(root,export_id,'attachment-prepared-start.json')
    fields={'schema','claim_file','plan_export_id','session_plan_sha256','delivery','retry_allowed','progression_authority'}
    if (type(report) is not dict or set(report)!=fields or report['schema']!='rocell.prepared_start_result.v1'
            or report['retry_allowed'] is not False or report['progression_authority'] is not False):
        raise ValueError('Invalid prepared start export')
    document,_=_read(root,report['plan_export_id'],'attachment-session-plan.json')
    challenge,_=_read(root,report['plan_export_id'],'attachment-start-challenge.json')
    _challenge_bytes(challenge)
    plan=SessionPlan(canonical(document))
    if (plan.sha256!=report['session_plan_sha256'] or document.get('schema')!='rocell.session_plan.v3'
            or document.get('origin')!='DEVICE_CAPTURE' or document['command']['boot_id']!=challenge['boot_id']):
        raise ValueError('Prepared plan identity mismatch')
    delivery=report['delivery']
    if (type(delivery) is not dict or delivery.get('schema')!='rocell.host_start_delivery.v1'
            or delivery.get('session_plan_sha256')!=plan.sha256
            or delivery.get('boot_id')!=challenge['boot_id']
            or delivery.get('command_id')!=document['command']['command_id']
            or delivery.get('retry_allowed') is not False or delivery.get('progression_authority') is not False
            or delivery.get('endpoint_verified') is not False
            or delivery.get('result') not in ('CONNECTION_UNVERIFIED','DELIVERY_UNCERTAIN',
                'CONTROLLER_REPORTED_ACCEPTANCE','CONTROLLER_REPORTED_REJECTION')):
        raise ValueError('Delivery identity or outcome mismatch')
    identity=canonical(dict(boot_id=challenge['boot_id'],nonce=challenge['nonce']))
    expected_name='diagnostic-start-'+hashlib.sha256(identity).hexdigest()+'.json'
    if report['claim_file']!=expected_name:raise ValueError('Start claim identity mismatch')
    claim_path=contained_path(root,expected_name,label='start claim')
    actual=read_bounded_regular_file(claim_path,maximum_bytes=2048)
    expected=canonical(dict(schema='rocell.host_start_claim.v1',plan_export_id=report['plan_export_id'],
        session_plan_sha256=plan.sha256,challenge_sha256=hashlib.sha256(canonical(challenge)).hexdigest(),
        state='CONSUMED_BEFORE_SEND',retry_allowed=False))
    if actual!=expected:raise ValueError('Start claim content mismatch; no recovery or resend')
    return report,digest,plan


def collect_started_run(root,prepared_export_id,get_bytes):
    root=Path(root).resolve()
    _,prepared_digest,plan=_prepared(root,prepared_export_id)
    doc=plan.to_dict()
    captured=collect_planned_run(root,get_bytes,doc['command'],doc['policy'],
        base64.b64decode(doc['sent_base64'],validate=True),doc['schedule'],origin=doc['origin'],
        baseline_policy=doc['baseline_policy'],whole_arm_policy=doc['whole_arm_policy'])
    run_id=Path(captured['export_path']).name
    _,run_digest=_read(root,run_id,'attachment-planned-run.json')
    report=dict(schema='rocell.started_run.v1',prepared_export_id=prepared_export_id,
        prepared_sha256=prepared_digest,planned_run_export_id=run_id,planned_run_sha256=run_digest,
        session_plan_sha256=plan.sha256,retry_allowed=False,progression_authority=False)
    exporter=WizardDiagnosticExporter(root);exporter.prepare(create=True)
    receipt=exporter.export({'mode':'started-diagnostic-review'},[],attachments={'started-run.json':canonical(report)})
    path=Path(receipt['path'])
    if not verify_export(path)['valid']:raise ValueError('Started run export verification failed')
    replay=replay_started_run(root,path.name)
    return dict(report,export_path=str(path),export_verified=True,replay_verified=True,outcome=replay['outcome'])


def replay_started_run(root,export_id):
    root=Path(root).resolve();report,_=_read(root,export_id,'attachment-started-run.json')
    fields={'schema','prepared_export_id','prepared_sha256','planned_run_export_id','planned_run_sha256',
            'session_plan_sha256','retry_allowed','progression_authority'}
    if (type(report) is not dict or set(report)!=fields or report['schema']!='rocell.started_run.v1'
            or report['retry_allowed'] is not False or report['progression_authority'] is not False):
        raise ValueError('Invalid started run')
    prepared,digest,plan=_prepared(root,report['prepared_export_id'])
    run,run_digest=_read(root,report['planned_run_export_id'],'attachment-planned-run.json')
    if (digest!=report['prepared_sha256'] or run_digest!=report['planned_run_sha256']
            or plan.sha256!=report['session_plan_sha256'] or run['plan_sha256']!=plan.sha256):
        raise ValueError('Started run linkage mismatch')
    result=replay_planned_run(root,report['planned_run_export_id'])
    return dict(matches=True,outcome=result['outcome'],delivery=prepared['delivery'],
                prepared_export_id=report['prepared_export_id'],progression_authority=False,retry_allowed=False)
