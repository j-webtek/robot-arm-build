"""Link one consumed startup attempt to read-only endpoint review. Never sends."""
import hashlib
from pathlib import Path

from .first_motion_contract import canonical
from .product_ghost_export_review import _read
from .physical_onboarding_durability import contained_path, read_bounded_regular_file
from .servo_start_authorization import _challenge_bytes
from .startup_command_contract import StartupSessionPlan, validate_startup_plan
from .startup_planned_run import collect_startup_run, replay_startup_run
from .wizard_diagnostic_coordinator import decode_diagnostic_json
from .wizard_diagnostic_export import WizardDiagnosticExporter, verify_export


def _prepared(root, export_id):
    report, digest = _read(root, export_id, 'attachment-prepared-startup.json')
    fields = {'schema', 'claim_file', 'plan_export_id', 'startup_plan_sha256', 'delivery',
              'retry_allowed', 'progression_authority'}
    if (type(report) is not dict or set(report) != fields or
            report['schema'] != 'rocell.prepared_startup_result.v1' or
            report['retry_allowed'] is not False or report['progression_authority'] is not False):
        raise ValueError('Invalid prepared startup record')
    document, _ = _read(root, report['plan_export_id'], 'attachment-startup-plan.json')
    context, _ = _read(root, report['plan_export_id'], 'attachment-startup-context.json')
    challenge, _ = _read(root, report['plan_export_id'], 'attachment-start-challenge.json')
    _challenge_bytes(challenge)
    if (type(context) is not dict or set(context) != {'boot_id', 'approved_policy'} or
            context['boot_id'] != challenge['boot_id']):
        raise ValueError('Startup context/challenge mismatch')
    plan = StartupSessionPlan(canonical(document))
    doc = validate_startup_plan(plan, context['boot_id'], context['approved_policy'])
    plan_hash = hashlib.sha256(plan.encoded).hexdigest()
    if report['startup_plan_sha256'] != plan_hash or doc['origin'] != 'DEVICE_CAPTURE':
        raise ValueError('Startup prepared plan mismatch')
    delivery = report['delivery']
    base = {'schema', 'connection_attempted', 'transmission_attempted', 'retry_allowed',
        'progression_authority', 'endpoint_verified', 'result', 'startup_plan_sha256', 'boot_id', 'command_id'}
    terminal = ('CONTROLLER_REPORTED_ACCEPTANCE', 'CONTROLLER_REPORTED_REJECTION')
    result = delivery.get('result') if type(delivery) is dict else None
    expected = base | ({'response_body', 'response_sha256'} if result in terminal else set())
    if (type(delivery) is not dict or set(delivery) != expected or
            delivery['schema'] != 'rocell.host_startup_delivery.v1' or
            delivery['startup_plan_sha256'] != plan_hash or delivery['boot_id'] != context['boot_id'] or
            delivery['command_id'] != doc['command']['command_id'] or
            any(delivery[key] is not False for key in ('retry_allowed','progression_authority','endpoint_verified')) or
            delivery['connection_attempted'] is not True or
            result not in (*terminal, 'CONNECTION_UNVERIFIED', 'DELIVERY_UNCERTAIN') or
            delivery['transmission_attempted'] is not (result != 'CONNECTION_UNVERIFIED')):
        raise ValueError('Startup delivery evidence mismatch')
    if result in terminal:
        if type(delivery['response_body']) is not str:raise ValueError('Invalid response body')
        body = delivery['response_body'].encode('ascii')
        accepted = result == 'CONTROLLER_REPORTED_ACCEPTANCE'
        if (hashlib.sha256(body).hexdigest() != delivery['response_sha256'] or
                canonical(decode_diagnostic_json(body,maximum=256)) != canonical(dict(accepted=accepted,retry_allowed=False))):
            raise ValueError('Startup acceptance response mismatch')
    identity = canonical(dict(boot_id=challenge['boot_id'], nonce=challenge['nonce']))
    claim_name = 'diagnostic-start-' + hashlib.sha256(identity).hexdigest() + '.json'
    if report['claim_file'] != claim_name:raise ValueError('Startup claim identity mismatch')
    path = contained_path(root, claim_name, label='startup claim')
    expected_claim = dict(schema='rocell.host_startup_claim.v1', plan_export_id=report['plan_export_id'],
        startup_plan_sha256=plan_hash, challenge_sha256=hashlib.sha256(canonical(challenge)).hexdigest(),
        state='CONSUMED_BEFORE_SEND', retry_allowed=False)
    if read_bounded_regular_file(path,maximum_bytes=2048) != canonical(expected_claim):
        raise ValueError('Startup claim changed; do not resend')
    return report, digest, plan, context


def collect_started_startup(root, prepared_export_id, get_bytes):
    root = Path(root).resolve()
    _, prepared_digest, plan, context = _prepared(root, prepared_export_id)
    captured = collect_startup_run(root, get_bytes, plan, boot_id=context['boot_id'],
        approved_policy=context['approved_policy'])
    run_id = Path(captured['export_path']).name
    _, run_digest = _read(root, run_id, 'attachment-startup-run.json')
    report = dict(schema='rocell.started_startup_run.v1', prepared_export_id=prepared_export_id,
        prepared_sha256=prepared_digest, startup_run_export_id=run_id, startup_run_sha256=run_digest,
        startup_plan_sha256=hashlib.sha256(plan.encoded).hexdigest(), retry_allowed=False,
        progression_authority=False)
    exporter = WizardDiagnosticExporter(root); exporter.prepare(create=True)
    saved = exporter.export({'mode':'started-startup-review'}, [],
        attachments={'started-startup-run.json':canonical(report)})
    path = Path(saved['path'])
    if not verify_export(path)['valid']:raise ValueError('Started startup export verification failed')
    replay = replay_started_startup(root, path.name)
    return dict(report, export_path=str(path), export_verified=True,
        replay_verified=replay['matches'], outcome=replay['outcome'], delivery=replay['delivery'])


def replay_started_startup(root, export_id):
    root = Path(root).resolve()
    report, _ = _read(root, export_id, 'attachment-started-startup-run.json')
    fields = {'schema','prepared_export_id','prepared_sha256','startup_run_export_id',
              'startup_run_sha256','startup_plan_sha256','retry_allowed','progression_authority'}
    if (type(report) is not dict or set(report) != fields or report['schema'] != 'rocell.started_startup_run.v1' or
            report['retry_allowed'] is not False or report['progression_authority'] is not False):
        raise ValueError('Invalid started startup linkage')
    prepared, digest, plan, context = _prepared(root, report['prepared_export_id'])
    run, run_digest = _read(root, report['startup_run_export_id'], 'attachment-startup-run.json')
    linked_plan, _ = _read(root, run['plan_export_id'], 'attachment-startup-plan.json')
    linked_context, _ = _read(root, run['plan_export_id'], 'attachment-startup-context.json')
    if (digest != report['prepared_sha256'] or run_digest != report['startup_run_sha256'] or
            hashlib.sha256(plan.encoded).hexdigest() != report['startup_plan_sha256'] or
            canonical(linked_plan) != plan.encoded or canonical(linked_context) != canonical(context)):
        raise ValueError('Started startup plan/context linkage mismatch')
    replay = replay_startup_run(root, report['startup_run_export_id'])
    return dict(matches=True, outcome=replay['outcome'], delivery=prepared['delivery'],
        prepared_export_id=report['prepared_export_id'], retry_allowed=False, progression_authority=False)
