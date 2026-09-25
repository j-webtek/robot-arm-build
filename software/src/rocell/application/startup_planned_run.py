"""Read-only startup collection, durable review and deterministic replay.

No start token, provisioning, reset or motion request is constructed here.
"""
from pathlib import Path

from .first_motion_contract import canonical
from .product_ghost_export_review import _read
from .servo_transport_export import capture_transport_export, replay_transport_export
from .startup_command_contract import StartupSessionPlan, validate_startup_plan
from .startup_session_assessment import assess_startup_session
from .wizard_diagnostic_export import WizardDiagnosticExporter, verify_export


def _outcome(snapshot, plan, boot_id, policy):
    try:
        assessment = assess_startup_session(snapshot, plan, boot_id=boot_id, approved_policy=policy)
        return dict(status='ASSESSED', assessment=assessment)
    except (ValueError, KeyError, TypeError, OverflowError, AttributeError):
        # Preserve incomplete evidence; never fall back to normal-mode admission.
        return dict(status='INCONCLUSIVE', assessment=None)


def collect_startup_run(root, get_bytes, plan, *, boot_id, approved_policy):
    validate_startup_plan(plan, boot_id, approved_policy)
    root = Path(root).resolve()
    exporter = WizardDiagnosticExporter(root); exporter.prepare(create=True)
    context = dict(boot_id=boot_id, approved_policy=approved_policy)
    prepared = exporter.export({'mode': 'startup-plan'}, [], attachments={
        'startup-plan.json': plan.encoded, 'startup-context.json': canonical(context)})
    pre_id = Path(prepared['path']).name
    retained, digest = _read(root, pre_id, 'attachment-startup-plan.json')
    stored_context, context_digest = _read(root, pre_id, 'attachment-startup-context.json')
    if canonical(retained) != plan.encoded or canonical(stored_context) != canonical(context):
        raise ValueError('Persisted startup expectations differ')
    captured = capture_transport_export(root, get_bytes, startup=True)
    capture_id = Path(captured['export_path']).name
    _, capture_digest = _read(root, capture_id, 'attachment-transport-capture.json')
    report = dict(schema='rocell.startup_planned_run.v1', plan_export_id=pre_id,
        plan_sha256=digest, context_sha256=context_digest, capture_export_id=capture_id,
        capture_sha256=capture_digest,
        outcome=_outcome(captured['summary'], plan, boot_id, approved_policy),
        progression_authority=False)
    saved = exporter.export({'mode': 'startup-review'}, [],
        attachments={'startup-run.json': canonical(report)})
    path = Path(saved['path'])
    if not verify_export(path)['valid']: raise ValueError('Startup review export failed')
    replay = replay_startup_run(root, path.name)
    return dict(report, export_path=str(path), export_verified=True, replay_verified=replay['matches'])


def replay_startup_run(root, export_id):
    root = Path(root).resolve()
    report, _ = _read(root, export_id, 'attachment-startup-run.json')
    fields = {'schema', 'plan_export_id', 'plan_sha256', 'context_sha256',
              'capture_export_id', 'capture_sha256', 'outcome', 'progression_authority'}
    if (type(report) is not dict or set(report) != fields or
            report['schema'] != 'rocell.startup_planned_run.v1' or report['progression_authority'] is not False):
        raise ValueError('Invalid startup run')
    doc, digest = _read(root, report['plan_export_id'], 'attachment-startup-plan.json')
    context, context_digest = _read(root, report['plan_export_id'], 'attachment-startup-context.json')
    _, capture_digest = _read(root, report['capture_export_id'], 'attachment-transport-capture.json')
    if (digest != report['plan_sha256'] or context_digest != report['context_sha256'] or
            capture_digest != report['capture_sha256']):
        raise ValueError('Startup retained evidence identity mismatch')
    if type(context) is not dict or set(context) != {'boot_id', 'approved_policy'}:
        raise ValueError('Invalid startup review context')
    plan = StartupSessionPlan(canonical(doc))
    validate_startup_plan(plan, context['boot_id'], context['approved_policy'])
    captured = replay_transport_export(root, report['capture_export_id'])
    actual = _outcome(captured['summary'], plan, context['boot_id'], context['approved_policy'])
    if canonical(actual) != canonical(report['outcome']):
        raise ValueError('Startup replay assessment mismatch')
    return dict(matches=True, outcome=actual, progression_authority=False)
