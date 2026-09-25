"""One boot-bound startup trial; no reset, retries, compensation or second move."""
from pathlib import Path
import time

from .first_motion_contract import canonical
from .physical_onboarding_durability import publish_reservation_bytes
from .servo_start_authorization import _hex, _key
from .servo_transport_export import capture_transport_export
from .startup_first_trial import build_first_trial
from .startup_prepared_start import send_prepared_startup
from .startup_started_run import collect_started_startup
from .wizard_diagnostic_export import WizardDiagnosticExporter, verify_export


def run_first_trial(root, *, configuration, expected_boot, command_id, key,
                    get_bytes, discover, sender, pause=time.sleep):
    """Caller supplies approved physical setup and inert device adapters.

    Loading the private key is the caller's preflight responsibility, before this
    function requests a short-lived challenge. A 4-second post-send observation
    delay covers the six 500 ms samples plus startup acquisition. If the device
    remains nonterminal, collection reports inconclusive rather than retrying.
    Uncertain delivery may be followed by this single read-only evidence capture,
    never another command. The caller must not treat arrival as displacement.
    """
    _hex(expected_boot, 16)
    _key(key)
    plan = build_first_trial(configuration, boot_id=expected_boot, command_id=command_id,
                             origin='DEVICE_CAPTURE')
    root = Path(root).resolve()
    exporter = WizardDiagnosticExporter(root)
    exporter.prepare(create=True)
    before = capture_transport_export(root, get_bytes, startup=True)
    status = before['summary'].get('status')
    if (type(status) is not dict or status['instance_id'] != expected_boot or
            status['state'] != 'IDLE' or status['reason'] != 'NOT_CONFIGURED' or
            status['records'] != 0 or status['storage_fault'] is not False):
        raise ValueError('Fresh uninitialized startup boot required; do not reset automatically')
    # Unlike a per-nonce claim, this also prevents a fresh process from repeating
    # challenge discovery on the same boot after an interrupted pre-send path.
    publish_reservation_bytes(root, 'first-startup-trial-' + expected_boot + '.json',
        canonical(dict(schema='rocell.first_startup_trial_claim.v1', boot_id=expected_boot,
            command_id=command_id, retry_allowed=False)), maximum_bytes=2048)
    preview = exporter.export({'mode': 'first-startup-trial-plan'}, [],
        attachments={'startup-plan.json': plan.encoded})
    if not verify_export(Path(preview['path']))['valid']:
        raise ValueError('Trial preview export failed')
    try:
        discovered = discover(expected_boot)
        prepared = send_prepared_startup(root, sender, plan, discovered['challenge'], key,
            approved_policy=configuration['startup_policy'])
        # Never poll by issuing new start commands; the hardware owner handles
        # its finite acquisition schedule independently of this host wait.
        pause(4.0)
        return collect_started_startup(root, Path(prepared['export_path']).name, get_bytes)
    except BaseException:
        # Fixed failure text only; preserve consumed claims even on export failure.
        exporter.export({'mode': 'first-startup-trial-stopped'}, [], attachments={
            'trial-stopped.json': canonical(dict(boot_id=expected_boot, command_id=command_id,
                retry_allowed=False, endpoint_verified=False, automatic_reset=False))})
        raise
