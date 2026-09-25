"""Prepare locally, or explicitly execute one previously reviewed elbow trial.

No serial/reset/power/configuration actions are included. The caller must arrange
a fresh controller startup and motor-powered clear test setup before live mode.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys

from rocell.application.first_motion_contract import canonical
from rocell.application.startup_first_trial import build_first_trial
from rocell.application.startup_command_contract import validate_startup_plan


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--prepare-only', action='store_true')
    mode.add_argument('--authorized-one-move', action='store_true')
    parser.add_argument('--boot-id', required=True)
    parser.add_argument('--command-id', required=True)
    options = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    config = json.loads((root / 'docs/startup-r6-policy-draft.json').read_bytes())
    plan = build_first_trial(config, boot_id=options.boot_id, command_id=options.command_id,
                             origin='SIMULATION' if options.prepare_only else 'DEVICE_CAPTURE')
    doc = validate_startup_plan(plan, options.boot_id, config['startup_policy'])
    if options.prepare_only:
        print(json.dumps(dict(status='OFFLINE_PLAN_VALIDATED', hardware_access=False,
            plan_sha256=hashlib.sha256(plan.encoded).hexdigest(), command=doc['command'],
            fresh_delta_limit=doc['baseline_policy']['maximum_delta_counts'], schedule=doc['schedule'])))
        return
    # Local secret-loading and identity checks precede even passive network access.
    from provision_startup_r6 import check_private_acl, read_staged_key
    from rocell.providers.windows.diagnostic_image_store import load_image
    private = root / 'private-backups/controller-20260918-session1'
    check_private_acl(private)
    candidate = load_image(private / 'startup-r6-reviewed-candidate.dpapi')
    if hashlib.sha256(candidate).hexdigest() != '567d3cc0f20b2a5843bf27c7aac069f0df18782234f8579fae48a73604e569c6':
        raise ValueError('Installed startup candidate binding mismatch')
    sys.path.insert(0, str(root / '.firmware-tools/littlefs-review'))
    import littlefs
    if littlefs.__version__ != '0.19.0': raise ValueError('Unreviewed LittleFS version')
    key = read_staged_key(candidate, littlefs)
    from rocell.application.servo_diagnostic_http import DiagnosticHTTPReader
    from rocell.application.servo_diagnostic_challenge import DiagnosticChallengeReader
    from rocell.application.startup_prepared_start import StartupStartSender
    from rocell.application.startup_first_trial_run import run_first_trial
    result = run_first_trial(root / 'runs/wizard-exports', configuration=config,
        expected_boot=options.boot_id, command_id=options.command_id, key=key,
        get_bytes=DiagnosticHTTPReader('192.168.0.225'),
        discover=DiagnosticChallengeReader('192.168.0.225').discover,
        sender=StartupStartSender('192.168.0.225', 8081, config['startup_policy']))
    print(json.dumps(result))


if __name__ == '__main__':
    main()
