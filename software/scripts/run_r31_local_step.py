"""One reviewed r31 local shoulder step; no restart, retry or return."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

from rocell.application.local_shoulder_step_runner import run_local_step
from rocell.application.shoulder_session_http import ShoulderSessionHTTP
from rocell.application.supported_recovery_installation import review_recovery_startup


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--startup-export', required=True)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--preflight-only', action='store_true')
    mode.add_argument('--authorized-local-step', action='store_true')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    binding = review_recovery_startup(root, args.startup_export, revision=31)
    exports = root / 'runs/wizard-exports'
    boot = binding['expected_boot']
    claims = ('local-step-' + boot, 'shoulder-session-' + boot, 'pose-observation-' + boot,
              'first-hold-trial-' + boot, 'supported-recovery-trial-' + boot,
              'held-pair-trial-' + hashlib.sha256(boot.encode()).hexdigest())
    if any((exports / (name + '.json')).exists() for name in claims):
        raise ValueError('Boot already reserved; no retry')
    if args.preflight_only:
        print(json.dumps(dict(status='R31_LOCAL_STEP_PREFLIGHT_VERIFIED', expected_boot=boot,
                              hardware_access=False, key_extracted=False, movement_started=False)))
        return

    # Reuse the reviewed private filesystem key source without writing plaintext.
    from provision_startup_r6 import check_private_acl
    from provision_hold_r7 import read_hold_key
    from rocell.providers.windows.diagnostic_image_store import load_image
    private = root / 'private-backups/controller-20260918-session1'
    check_private_acl(private)
    image = load_image(private / 'observed-pose-plus10-candidate.dpapi')
    if (len(image) != 0x160000 or hashlib.sha256(image).hexdigest() !=
            '45320bab56ec1d8e889078a50e2aa0ef79d4d65c59e5dcb89c7a7880f08e7267'):
        raise ValueError('Installed key-source identity differs')
    sys.path.insert(0, str(root / '.firmware-tools/littlefs-review'))
    import littlefs
    if not Path(littlefs.__file__).resolve().is_relative_to((root / '.firmware-tools/littlefs-review').resolve()):
        raise ValueError('Unexpected filesystem implementation')
    key = read_hold_key(image, littlefs)
    result = run_local_step(exports, boot=boot, key=key,
        exchange=ShoulderSessionHTTP(binding['address'], local_step_capability=True, settling_capability=True),
        authorized=True, origin='DEVICE_CAPTURE', software_root=root, startup_export=args.startup_export)
    report = result['report']
    print(json.dumps(dict(export_path=result['export_path'], state=report['state'],
        record_count=len(report['records']), error_type=report.get('error_type'),
        controller_reason=report.get('controller_reason'), final_positions=report.get('final_positions'),
        retry=False)))


if __name__ == '__main__':
    main()
