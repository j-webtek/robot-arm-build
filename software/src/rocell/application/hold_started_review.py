"""Link simulated native capture to one saved hold attempt. Never sends/opens I/O."""
import hashlib
from pathlib import Path

from .first_motion_contract import canonical
from .hold_bound_replay import export_bound_simulation, replay_bound_simulation_export
from .hold_command_contract import HoldPlan, validate_hold_plan
from .physical_onboarding_durability import contained_path, read_bounded_regular_file
from .product_ghost_export_review import _read
from .servo_diagnostic_contract import _integer
from .servo_start_authorization import _challenge_bytes
from .wizard_diagnostic_coordinator import decode_diagnostic_json
from .wizard_diagnostic_export import WizardDiagnosticExporter


def _prepared(root, export_id):
    report, digest = _read(root, export_id, 'attachment-prepared-hold.json')
    fields = {'schema', 'claim_file', 'plan_export_id', 'hold_plan_sha256', 'policy_sha256',
              'delivery', 'retry_allowed', 'progression_authority'}
    if (type(report) is not dict or set(report) != fields or
            report['schema'] != 'rocell.prepared_hold_result.v1' or
            report['retry_allowed'] is not False or report['progression_authority'] is not False):
        raise ValueError('Invalid prepared hold')
    plan, _ = _read(root, report['plan_export_id'], 'attachment-hold-plan.json')
    policy, _ = _read(root, report['plan_export_id'], 'attachment-hold-policy.json')
    challenge, _ = _read(root, report['plan_export_id'], 'attachment-start-challenge.json')
    _challenge_bytes(challenge)
    frozen = HoldPlan(canonical(plan), canonical(policy))
    validate_hold_plan(frozen, boot_id=challenge['boot_id'], approved_policy=policy)
    plan_hash = hashlib.sha256(frozen.encoded).hexdigest()
    if report['hold_plan_sha256'] != plan_hash or report['policy_sha256'] != plan['policy_sha256']:
        raise ValueError('Prepared plan hashes differ')
    identity = canonical(dict(boot_id=challenge['boot_id'], nonce=challenge['nonce']))
    claim_name = 'diagnostic-start-' + hashlib.sha256(identity).hexdigest() + '.json'
    if report['claim_file'] != claim_name:
        raise ValueError('Nonce claim mismatch')
    claim = dict(schema='rocell.host_hold_claim.v1', plan_export_id=report['plan_export_id'],
                 hold_plan_sha256=plan_hash, policy_sha256=plan['policy_sha256'],
                 challenge_sha256=hashlib.sha256(canonical(challenge)).hexdigest(),
                 state='CONSUMED_BEFORE_SEND', retry_allowed=False)
    path = contained_path(root, claim_name, label='hold nonce claim')
    if read_bounded_regular_file(path, maximum_bytes=2048) != canonical(claim):
        raise ValueError('Consumed hold claim changed')
    delivery = report['delivery']
    if type(delivery) is not dict or delivery.get('schema') != 'rocell.host_hold_delivery.v1':
        raise ValueError('Hold delivery schema')
    if any(delivery.get(k) is not False for k in ('retry_allowed', 'endpoint_verified', 'progression_authority')):
        raise ValueError('Delivery authority mismatch')
    result = delivery.get('result')
    terminal = ('CONTROLLER_REPORTED_ACCEPTANCE', 'CONTROLLER_REPORTED_REJECTION')
    if result not in (*terminal, 'DELIVERY_UNCERTAIN', 'CONNECTION_UNVERIFIED', 'PREPARATION_REJECTED'):
        raise ValueError('Unknown delivery outcome')
    if delivery.get('reason') == 'ADAPTER_EXCEPTION':
        if set(delivery) != {'schema', 'result', 'reason', 'retry_allowed', 'endpoint_verified', 'progression_authority'} or result != 'DELIVERY_UNCERTAIN':
            raise ValueError('Invalid uncertain adapter report')
    else:
        base = {'schema', 'connection_attempted', 'transmission_attempted', 'retry_allowed',
                'progression_authority', 'endpoint_verified', 'result', 'hold_plan_sha256',
                'policy_sha256', 'boot_id', 'command_id'}
        if (set(delivery) != base | ({'response_body', 'response_sha256'} if result in terminal else set()) or
                delivery['hold_plan_sha256'] != plan_hash or delivery['policy_sha256'] != plan['policy_sha256'] or
                delivery['boot_id'] != plan['boot_id'] or delivery['command_id'] != plan['command_id'] or
                type(delivery['connection_attempted']) is not bool or type(delivery['transmission_attempted']) is not bool):
            raise ValueError('Delivery identity mismatch')
        if result in (*terminal, 'DELIVERY_UNCERTAIN') and not (delivery['connection_attempted'] and delivery['transmission_attempted']):
            raise ValueError('Delivery transmission missing')
        if result in terminal:
            body = delivery['response_body'].encode('ascii')
            if (hashlib.sha256(body).hexdigest() != delivery['response_sha256'] or
                    canonical(decode_diagnostic_json(body, maximum=256)) != canonical(
                        dict(accepted=result == terminal[0], retry_allowed=False))):
                raise ValueError('Delivery response mismatch')
    return report, digest, plan, policy, challenge


def _challenge_window(records, challenge):
    if type(records) is not list or not records:
        raise ValueError('Capture missing')
    for record in records:
        times = []
        if record.get('schema') == 'rocell.hold_authorization.v1':
            times.append(record['received_us'])
        elif record.get('schema') == 'rocell.hold_snapshot.v1':
            for row in record['reads']:
                times.extend(row[3][1:3])
        elif record.get('schema') == 'rocell.hold_action.v1':
            times.extend((record['started_us'], record['finished_us']))
        for value in times:
            _integer(value)
            if not challenge['issued_us'] <= value < challenge['expires_us']:
                raise ValueError('Capture outside admitted challenge window')


def review_prepared_hold_simulation(root, prepared_export_id, records):
    root = Path(root).resolve()
    _, digest, plan, policy, challenge = _prepared(root, prepared_export_id)
    _challenge_window(records, challenge)
    capture = export_bound_simulation(root, records, expected_plan=plan, expected_policy=policy)
    capture_id = Path(capture['path']).name
    _, capture_digest = _read(root, capture_id, 'attachment-hold-records.json')
    link = dict(schema='rocell.started_hold_simulation.v1', prepared_export_id=prepared_export_id,
                prepared_sha256=digest, capture_export_id=capture_id, capture_sha256=capture_digest,
                retry_allowed=False, progression_authority=False)
    exporter = WizardDiagnosticExporter(root)
    exporter.prepare(create=True)
    saved = exporter.export({'mode': 'started-hold-simulation'}, [],
        attachments={'started-hold.json': canonical(link)})
    replay_started_hold_simulation(root, Path(saved['path']).name)
    return saved


def replay_started_hold_simulation(root, export_id):
    root = Path(root).resolve()
    link, _ = _read(root, export_id, 'attachment-started-hold.json')
    if (set(link) != {'schema', 'prepared_export_id', 'prepared_sha256', 'capture_export_id',
                      'capture_sha256', 'retry_allowed', 'progression_authority'} or
            link['schema'] != 'rocell.started_hold_simulation.v1' or
            link['retry_allowed'] is not False or link['progression_authority'] is not False):
        raise ValueError('Invalid hold linkage')
    prepared, digest, plan, policy, challenge = _prepared(root, link['prepared_export_id'])
    records, capture_digest = _read(root, link['capture_export_id'], 'attachment-hold-records.json')
    retained_plan, _ = _read(root, link['capture_export_id'], 'attachment-hold-plan.json')
    retained_policy, _ = _read(root, link['capture_export_id'], 'attachment-hold-policy.json')
    if (digest != link['prepared_sha256'] or capture_digest != link['capture_sha256'] or
            canonical(plan) != canonical(retained_plan) or canonical(policy) != canonical(retained_policy)):
        raise ValueError('Hold linkage changed')
    _challenge_window(records, challenge)
    assessment = replay_bound_simulation_export(root / link['capture_export_id'])
    return dict(matches=True, origin='SIMULATION', assessment=assessment,
                delivery=prepared['delivery'], retry_allowed=False, progression_authority=False)
