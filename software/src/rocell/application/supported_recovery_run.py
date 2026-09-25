"""One explicitly approved recovery trial; no install/reset/retry or next move."""
import hashlib
import json
from pathlib import Path
import time

from .first_motion_contract import canonical
from .held_pair_capabilities import read_pair_capabilities
from .held_pair_challenge_http import request_recovery_challenge
from .hold_transport_export import capture_hold_transport, capture_recovery_transport
from .hold_transport_snapshot import HoldHTTPReader, RecoveryHTTPReader
from .physical_onboarding_durability import publish_reservation_bytes
from .product_ghost_export_review import _read
from .r10_provisioned_evidence import POLICY
from .servo_start_authorization import _key
from .supported_recovery_installation import review_recovery_startup
from .supported_recovery_start import freeze_recovery_plan, RecoveryStartSender, send_prepared_recovery
from .supported_recovery_review import export_recovery, replay_recovery
from .wizard_diagnostic_export import WizardDiagnosticExporter
from .observed_pose_installation import review_observed_startup
from .observed_pose_recovery import recovery_policy_from_candidate, COMMAND as OBSERVED_COMMAND


def run_supported_recovery(software_root, *, startup_export_id, key,
                           authorized_recovery=False, pause=time.sleep, profile='supported',
                           stage_export_id=None, installation_export_id=None):
    if authorized_recovery is not True:
        raise ValueError('Explicit one-shot recovery approval required')
    _key(key)
    if profile not in ('supported', 'six_count', 'observed_pose'):
        raise ValueError('Reviewed recovery profile required')
    root = Path(software_root).resolve()
    # A six-count policy must bind to the reviewed successor, never the installed
    # five-count runtime. Missing installation evidence fails before network I/O.
    if profile == 'observed_pose':
        if not stage_export_id or not installation_export_id:
            raise ValueError('Observed-pose stage and installation receipts required')
        binding = review_observed_startup(root, startup_export=startup_export_id,
            stage_export=stage_export_id, installation_export=installation_export_id)
        policy = recovery_policy_from_candidate(root,
            binding['observed_pose_installation']['public_candidate_export'])
        hold = policy['hold_policy']; command = OBSERVED_COMMAND
        # Distinct policy/command, existing six-count wire and evidence schema.
        profile = 'six_count'
    else:
        if stage_export_id is not None or installation_export_id is not None:
            raise ValueError('Observed-pose receipts cannot qualify a legacy profile')
        binding = (review_recovery_startup(root, startup_export_id, revision=19)
                   if profile == 'six_count' else review_recovery_startup(root, startup_export_id))
        raw = (root / 'docs/hold-r7-supported-pose-draft.json').read_bytes()
        configuration = json.loads(raw)
        if hashlib.sha256(canonical(configuration)).hexdigest() != POLICY:
            raise ValueError('Reviewed source policy changed')
        hold = configuration['hold_policy'];hold['permit_explicit_enable'] = 0
        prefix = 'six_count' if profile == 'six_count' else 'supported'
        policy = dict(schema=f'rocell.{prefix}_recovery_policy.v1', hold_policy=hold,
                      initial_residual_counts=6 if profile == 'six_count' else 5)
        command = 'r18-six-count-recovery' if profile == 'six_count' else 'r15-supported-recovery'
    boot, address = binding['expected_boot'], binding['address']
    plan = freeze_recovery_plan(policy, boot_id=boot, command_id=command, profile=profile)
    exports = root / 'runs/wizard-exports'
    exporter = WizardDiagnosticExporter(exports);exporter.prepare(create=True)
    claim_name = 'supported-recovery-trial-'+boot+'.json'
    if (exports / claim_name).exists():
        raise ValueError('Recovery boot attempt consumed; no retry')
    before = capture_hold_transport(exports, HoldHTTPReader(address), expected_boot=boot)
    status = before['summary'].get('status', {})
    if (before['summary']['category'] != 'TRANSPORT_CAPTURED' or status.get('state') != 'IDLE' or
            status.get('reason') != 'NOT_CONFIGURED' or status.get('records') != 0 or
            status.get('storage_fault') is not False):
        raise ValueError('Fresh idle startup required')
    read_pair_capabilities(address=address, expected_boot=boot)
    binding_export = exporter.export({'mode': 'recovery-trial-intent'}, [], attachments={
        'recovery-binding.json': canonical(binding), 'recovery-plan.json': plan.encoded,
        'recovery-policy.json': plan.policy_encoded})
    retained, _ = _read(exports, Path(binding_export['path']).name, 'attachment-recovery-binding.json')
    if canonical(retained) != canonical(binding): raise ValueError('Recovery binding export changed')
    publish_reservation_bytes(exports, claim_name, canonical(dict(
        schema='rocell.recovery_trial_claim.v1', boot_id=boot,
        intent_export_id=Path(binding_export['path']).name,
        state='CONSUMED_BEFORE_PREPARE', retry_allowed=False)), maximum_bytes=2048)
    links = dict(intent_export_id=Path(binding_export['path']).name,
                 baseline_export_id=Path(before['export_path']).name)
    try:
        challenge = request_recovery_challenge(exports, expected_boot=boot, address=address)
        links['challenge_export_id'] = Path(challenge['export_path']).name
        discovery = challenge['report']['result']
        if discovery['category'] != 'CHALLENGE_RECEIVED':
            raise ValueError('Recovery preparation uncertain; do not retry')
        delivery = send_prepared_recovery(exports, RecoveryStartSender(address, 8081, policy, profile=profile),
            plan, discovery['challenge'], key, approved_policy=policy, profile=profile)
        links['delivery_export_id'] = Path(delivery['export_path']).name
        # Read-only evidence collection is useful even after uncertain delivery.
        # This wait exceeds the finite native hold deadline; it never retries.
        pause(hold['deadline_us']/1_000_000+1.0)
        transport = capture_recovery_transport(exports, RecoveryHTTPReader(address), expected_boot=boot, profile=profile)
        links['transport_export_id'] = Path(transport['export_path']).name
        records = transport['summary']['records']
        assessed = export_recovery(exports, records, expected_plan=json.loads(plan.encoded),
                                   expected_policy=policy, origin='DEVICE_CAPTURE', profile=profile)
        links['assessment_export_id'] = Path(assessed['path']).name
        result = replay_recovery(assessed['path'])
        complete = (transport['summary']['category'] == 'TRANSPORT_CAPTURED' and
                    delivery['delivery']['result'] == 'CONTROLLER_REPORTED_ACCEPTANCE' and
                    result['category'] == 'CONTROLLER_REPORTED_RECOVERY_VERIFIED')
        outcome = 'CONTROLLER_REPORTED_RECOVERY_VERIFIED' if complete else 'INCONCLUSIVE'
        report = dict(schema='rocell.supported_recovery_trial.v1', boot_id=boot, links=links,
                      category=outcome, retry_allowed=False, progression_authority=False)
    except Exception:
        report = dict(schema='rocell.supported_recovery_trial.v1', boot_id=boot, links=links,
            category='INCONCLUSIVE', reason='TRIAL_STOPPED', retry_allowed=False, progression_authority=False)
    exported = exporter.export({'mode': 'supported-recovery-trial'}, [],
                               attachments={'recovery-trial.json': canonical(report)})
    saved, _ = _read(exports, Path(exported['path']).name, 'attachment-recovery-trial.json')
    if canonical(saved) != canonical(report): raise ValueError('Recovery trial export changed; do not retry')
    return dict(report, export_path=exported['path'])
