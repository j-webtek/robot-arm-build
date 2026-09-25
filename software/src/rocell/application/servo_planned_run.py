"""Persist expectations before read-only collection; replay the linked evidence."""
from pathlib import Path
from .first_motion_contract import canonical
from .servo_session_plan import SessionPlan, freeze_session_plan, assess_planned_session
from .servo_transport_export import capture_transport_export,replay_transport_export
from .wizard_diagnostic_export import WizardDiagnosticExporter,verify_export
from .product_ghost_export_review import _read
from .servo_partial_session import assess_partial_session


def _outcome(snapshot,plan,*,allow_partial=True):
    try:
        return dict(status='ASSESSED',assessment=assess_planned_session(snapshot,plan))
    except (ValueError,KeyError,TypeError,OverflowError):
        # Raw evidence remains linked for investigation; no automatic retry.
        if not allow_partial:
            return dict(status='EVIDENCE_REJECTED',assessment=None)
        try:
            return dict(status='PARTIAL_FAILURE_ASSESSED',assessment=assess_partial_session(snapshot,plan))
        except (ValueError,KeyError,TypeError,OverflowError):
            return dict(status='EVIDENCE_REJECTED',assessment=None)


def collect_planned_run(root,get_bytes,command,policy,sent_bytes,schedule,*,origin,baseline_policy=None,whole_arm_policy=None):
    root=Path(root).resolve()
    plan=freeze_session_plan(command,policy,sent_bytes,schedule,origin=origin,baseline_policy=baseline_policy,whole_arm_policy=whole_arm_policy)
    exporter=WizardDiagnosticExporter(root);exporter.prepare(create=True)
    pre=exporter.export({'mode':'diagnostic-session-plan'},[],attachments={'session-plan.json':plan.encoded})
    pre_path=Path(pre['path'])
    retained,digest=_read(root,pre_path.name,'attachment-session-plan.json')
    if canonical(retained)!=plan.encoded:
        raise ValueError('Saved plan does not match frozen expectations')
    # First reader invocation happens only after the durable plan is verified.
    captured=capture_transport_export(root,get_bytes)
    capture_id=Path(captured['export_path']).name
    _,capture_digest=_read(root,capture_id,'attachment-transport-capture.json')
    outcome=_outcome(captured['summary'],plan)
    report=dict(schema='rocell.planned_diagnostic_run.v2',plan_export_id=pre_path.name,
        plan_sha256=plan.sha256,capture_export_id=capture_id,capture_sha256=capture_digest,
        outcome=outcome,progression_authority=False)
    receipt=exporter.export({'mode':'planned-diagnostic-review'},[],attachments={'planned-run.json':canonical(report)})
    path=Path(receipt['path'])
    if not verify_export(path)['valid']:raise ValueError('Run export verification failed')
    replay=replay_planned_run(root,path.name)
    return dict(report,export_path=str(path),export_verified=True,replay_verified=replay['matches'])


def replay_planned_run(root,export_id):
    root=Path(root).resolve()
    report,_=_read(root,export_id,'attachment-planned-run.json')
    fields={'schema','plan_export_id','plan_sha256','capture_export_id','capture_sha256','outcome','progression_authority'}
    if (type(report) is not dict or set(report)!=fields or report['schema'] not in ('rocell.planned_diagnostic_run.v1','rocell.planned_diagnostic_run.v2')
            or report['progression_authority'] is not False):raise ValueError('Invalid planned run')
    document,digest=_read(root,report['plan_export_id'],'attachment-session-plan.json')
    if SessionPlan(canonical(document)).sha256!=report['plan_sha256']:raise ValueError('Plan identity mismatch')
    _,digest=_read(root,report['capture_export_id'],'attachment-transport-capture.json')
    if digest!=report['capture_sha256']:raise ValueError('Capture identity mismatch')
    captured=replay_transport_export(root,report['capture_export_id'])
    # Preserve historical verdicts: v1 did not classify partial failures.
    actual=_outcome(captured['summary'],SessionPlan(canonical(document)),
        allow_partial=report['schema']=='rocell.planned_diagnostic_run.v2')
    if canonical(actual)!=canonical(report['outcome']):raise ValueError('Run assessment mismatch')
    return dict(matches=True,outcome=actual,progression_authority=False)
