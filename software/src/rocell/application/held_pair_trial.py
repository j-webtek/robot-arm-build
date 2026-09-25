"""Finite two-leg execution bridge for a trusted, separately admitted caller.

Not a browser endpoint or permission mechanism. The caller must establish the
reviewed installed image/configuration and powered-trial approval. This bridge
never installs, provisions, resets, retries, or performs recovery movements.
"""
import hashlib
import time
from pathlib import Path

from .first_motion_contract import canonical
from .held_pair_preparation import replay_held_pair_preparation
from .held_pair_capabilities import read_pair_capabilities
from .held_pair_challenge_http import request_pair_challenge
from .held_pair_receipt_workflow import authorize_pair_from_receipt
from .held_pair_delivery import send_authorized_pair
from .held_pair_observed_forward import collect_authorized_pair_forward
from .held_pair_observed_return import collect_authorized_pair_return
from .physical_onboarding_durability import publish_reservation_bytes, read_bounded_regular_file
from .product_ghost_export_review import _read
from .servo_diagnostic_http import DiagnosticHTTPReader
from .servo_start_authorization import _key
from .wizard_diagnostic_export import WizardDiagnosticExporter


class _StopTrial(Exception):
    pass


def run_admitted_pair(root, preparation_id, *, address, key, approved,
                      cancelled=lambda: False, http_port=80, command_port=8081,
                      pause=time.sleep):
    """Execute at most one forward and one evidence-gated return.

    ``approved`` must come from trusted host admission, never an untrusted request
    field. Cancellation prevents the next operation; it cannot stop a command
    already delivered. Any failure consumes the boot's trial reservation. Exports
    contain references and public diagnostics, never keys or signed tokens.
    """
    if approved is not True:
        raise ValueError('Separate powered pair admission required')
    _key(key)
    checked = DiagnosticHTTPReader(address, http_port)
    DiagnosticHTTPReader(address, command_port)  # Validate both before any I/O.
    root = Path(root).resolve()
    source = replay_held_pair_preparation(root, preparation_id)
    boot = source['preparation']['pair_plan']['boot_id']
    policy = source['preparation']['policy']
    deadline, gap = policy['deadline_us'], policy['maximum_gap_us']
    if any(type(value) is not int or value <= 0 for value in (deadline, gap)):
        raise ValueError('Positive integer observation timing required')
    # The native leg has separate prewrite and postwrite deadlines. Collect only
    # after both budgets plus a publication margin, never resend or poll to pass.
    observation_wait = (2 * deadline + gap) / 1_000_000 + 1.0
    if observation_wait > 30:
        raise ValueError('Observation wait exceeds bounded trial budget')
    exporter = WizardDiagnosticExporter(root)
    exporter.prepare(create=True)
    report = dict(schema='rocell.held_pair_trial.v1', preparation_export_id=preparation_id,
        preparation_sha256=source['preparation_sha256'], boot_id=boot,
        address=checked.address, http_port=http_port, command_port=command_port,
        phase='RESERVED', steps=[], retry_allowed=False, progression_authority=False,
        physical_tip_accuracy_verified=False, provenance_verified=False)
    claim = canonical(dict(schema='rocell.held_pair_trial_claim.v1', boot_id=boot,
        preparation_export_id=preparation_id, preparation_sha256=source['preparation_sha256'],
        state='CONSUMED_BEFORE_CAPABILITY_READ', retry_allowed=False))
    name = 'held-pair-trial-' + hashlib.sha256(boot.encode('ascii')).hexdigest() + '.json'
    publish_reservation_bytes(root, name, claim, maximum_bytes=2048)
    if read_bounded_regular_file(root/name, maximum_bytes=2048) != claim:
        raise ValueError('Trial claim differs; do not retry')

    def save():
        saved = exporter.export({'mode':'held-pair-trial'}, [],
            attachments={'held-pair-trial.json':canonical(report)})
        retained, _ = _read(root, Path(saved['path']).name, 'attachment-held-pair-trial.json')
        if canonical(retained) != canonical(report):
            raise ValueError('Trial export readback differs')
        return dict(export_path=saved['path'], report=retained)

    def check_cancel():
        if cancelled():
            raise _StopTrial('CANCELLED_BEFORE_NEXT_OPERATION')

    def remember(stage, result):
        report['phase'] = stage
        report['steps'].append(dict(stage=stage, export_id=Path(result['export_path']).name))
        save()  # Failure prevents the next hardware operation.

    save()
    try:
        check_cancel()
        report['capability_observation'] = read_pair_capabilities(
            address=address, expected_boot=boot, port=http_port)
        report['phase'] = 'CAPABILITIES_READ'
        save()
        forward_id = forward_delivery_id = None
        for leg in ('forward', 'return'):
            check_cancel()
            receipt = request_pair_challenge(root, operation='prepare' if leg=='forward' else 'return',
                expected_boot=boot, address=address, port=http_port)
            remember(leg.upper()+'_CHALLENGE', receipt)
            if receipt['report']['result']['category'] != 'CHALLENGE_RECEIVED':
                raise _StopTrial('CHALLENGE_UNCERTAIN')
            check_cancel()
            workflow = authorize_pair_from_receipt(root, Path(receipt['export_path']).name,
                preparation_id if leg=='forward' else forward_id, key, leg=leg,
                forward_delivery_export_id=None if leg=='forward' else forward_delivery_id)
            remember(leg.upper()+'_AUTHORIZED', workflow)
            check_cancel()
            delivered = send_authorized_pair(root, workflow['authorization'], leg=leg,
                address=address, port=command_port)
            remember(leg.upper()+'_DELIVERY', delivered)
            if delivered['report']['delivery']['result'] != 'CONTROLLER_REPORTED_ACCEPTANCE':
                raise _StopTrial('DELIVERY_NOT_ACCEPTED')
            check_cancel()
            pause(observation_wait)
            check_cancel()
            collector = collect_authorized_pair_forward if leg=='forward' else collect_authorized_pair_return
            observed = collector(root, workflow['authorization'].context_export_id,
                address=address, port=http_port)
            remember(leg.upper()+'_OBSERVATION', observed)
            if leg=='forward':
                assessment = observed['assessment']
                if (assessment.get('category') != 'CONTROLLER_REPORTED_ARRIVAL' or
                        assessment.get('stable_status_observed') is not True or
                        assessment.get('historical_anchor_matches') is not True or
                        assessment.get('controller_state') != 'AWAITING_EXPORT'):
                    raise _StopTrial('FORWARD_ENDPOINT_NOT_ELIGIBLE')
                forward_id = Path(observed['export_path']).name
                forward_delivery_id = Path(delivered['export_path']).name
            elif observed['review']['category'] != 'CONTROLLER_REPORTED_PAIR_ARRIVAL':
                raise _StopTrial('RETURN_ENDPOINT_NOT_VERIFIED')
        report['phase'] = 'CONTROLLER_REPORTED_PAIR_ARRIVAL'
    except _StopTrial as error:
        report.update(phase='STOPPED', reason=str(error))
    except Exception as error:
        # Dependency errors could include sensitive material; retain type only.
        report.update(phase='STOPPED', reason='OPERATION_OR_EXPORT_FAILURE', error_type=type(error).__name__)
    return save()
