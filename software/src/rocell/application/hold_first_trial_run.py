"""One explicitly admitted hold attempt; no provisioning, reset or recovery.

The caller must verify installed configuration and obtain powered-hold approval.
Load the private key before entry; never log it. This function is not approval.
"""
import json
from pathlib import Path
import time

from .first_motion_contract import canonical
from .hold_command_contract import freeze_hold_plan
from .hold_observed_review import collect_prepared_hold_observation
from .hold_prepared_start import HoldStartSender, send_prepared_hold
from .hold_transport_export import capture_hold_transport
from .hold_transport_snapshot import HoldHTTPReader
from .physical_onboarding_durability import publish_reservation_bytes
from .servo_diagnostic_challenge import DiagnosticChallengeReader
from .servo_start_authorization import _key
from .wizard_diagnostic_export import WizardDiagnosticExporter, verify_export


def run_first_hold(root, *, configuration, expected_boot, key, address,
                   authorized_powered_hold=False, pause=time.sleep):
    """Reserve the boot before challenge discovery, send once, then only observe.

    USB-only provisioning permission is insufficient. Even holding a fresh
    position may engage torque. Delivery uncertainty never triggers resend.
    A bounded wait covers the policy deadline; a still-active capture is
    inconclusive, not permission to retry. Failures preserve consumed claims.
    """
    if authorized_powered_hold is not True:
        raise ValueError('Separate powered-hold authorization required')
    _key(key)
    configuration = json.loads(canonical(configuration))
    if (type(configuration) is not dict or set(configuration) !=
            {'schema', 'command_id', 'start_port', 'hold_policy'} or
            configuration['schema'] != 'rocell.controller_hold.v1'):
        raise ValueError('Exact reviewed hold configuration required')
    policy = configuration['hold_policy']
    plan = freeze_hold_plan(policy, boot_id=expected_boot, command_id=configuration['command_id'])
    reader = HoldHTTPReader(address)
    challenge_reader = DiagnosticChallengeReader(address)
    sender = HoldStartSender(address, configuration['start_port'], policy)
    root = Path(root).resolve()
    exporter = WizardDiagnosticExporter(root)
    exporter.prepare(create=True)
    claim_name = 'first-hold-trial-' + expected_boot + '.json'
    if (root / claim_name).exists():
        raise ValueError('Hold boot attempt already consumed; do not reset automatically')
    before = capture_hold_transport(root, reader, expected_boot=expected_boot)
    status = before['summary'].get('status', {})
    if (before['summary']['category'] != 'TRANSPORT_CAPTURED' or
            status.get('state') != 'IDLE' or status.get('reason') != 'NOT_CONFIGURED' or
            status.get('records') != 0 or status.get('storage_fault') is not False):
        raise ValueError('Fresh unconfigured hold boot required')
    publish_reservation_bytes(root, claim_name, canonical(dict(
        schema='rocell.first_hold_trial_claim.v1', boot_id=expected_boot,
        command_id=configuration['command_id'], retry_allowed=False)), maximum_bytes=2048)
    try:
        preview = exporter.export({'mode': 'first-hold-trial-plan'}, [], attachments={
            'hold-plan.json': plan.encoded, 'hold-policy.json': plan.policy_encoded})
        if not verify_export(Path(preview['path']))['valid']:
            raise ValueError('Hold trial preview export failed')
        # Nothing slow (key loading, compilation, setup) belongs after this call.
        discovered = challenge_reader.discover(expected_boot)
        prepared = send_prepared_hold(root, sender, plan, discovered['challenge'], key,
                                      approved_policy=policy)
        pause(policy['deadline_us'] / 1_000_000 + 1.0)
        return collect_prepared_hold_observation(root, Path(prepared['export_path']).name,
                                                  address=address)
    except BaseException:
        exporter.export({'mode': 'first-hold-trial-stopped'}, [], attachments={
            'trial-stopped.json': canonical(dict(boot_id=expected_boot,
                command_id=configuration['command_id'], retry_allowed=False,
                automatic_reset=False, endpoint_verified=False))})
        raise
