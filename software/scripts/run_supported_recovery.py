"""Receipt-bound one-shot recovery. Never installs, resets or retries."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

from provision_startup_r6 import check_private_acl
from provision_hold_r7 import read_hold_key
from rocell.application.r10_provisioned_evidence import CANDIDATE
from rocell.application.supported_recovery_installation import review_recovery_startup
from rocell.application.supported_recovery_run import run_supported_recovery
from rocell.providers.windows.diagnostic_image_store import load_image


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--startup-export', required=True)
    parser.add_argument('--profile', choices=('supported', 'six_count', 'observed_pose'), default='supported')
    parser.add_argument('--stage-export')
    parser.add_argument('--installation-export')
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument('--preflight-only', action='store_true')
    modes.add_argument('--authorized-supported-recovery', action='store_true')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    revision = 21 if args.profile == 'observed_pose' else 19 if args.profile == 'six_count' else 16
    extra = {}
    if args.profile == 'observed_pose':
        if not args.stage_export or not args.installation_export:
            parser.error('Observed-pose recovery requires stage and installation receipts')
        from rocell.application.observed_pose_installation import review_observed_startup
        binding = review_observed_startup(root, startup_export=args.startup_export,
            stage_export=args.stage_export, installation_export=args.installation_export)
        extra = dict(stage_export_id=args.stage_export, installation_export_id=args.installation_export)
    else:
        if args.stage_export or args.installation_export:
            parser.error('Observed-pose receipts require the observed_pose profile')
        binding = review_recovery_startup(root, args.startup_export, revision=revision)
    private = root / 'private-backups/controller-20260918-session1'
    check_private_acl(private)
    candidate = load_image(private / 'pair-r10-settings-candidate.dpapi')
    if len(candidate) != 0x160000 or hashlib.sha256(candidate).hexdigest() != CANDIDATE:
        raise ValueError('Retained key-source image identity changed')
    claim = root / 'runs/wizard-exports' / ('supported-recovery-trial-'+binding['expected_boot']+'.json')
    if claim.exists(): raise ValueError('Recovery attempt already consumed')
    if args.preflight_only:
        print(json.dumps(dict(status=f'LOCAL_R{revision}_RECOVERY_PREFLIGHT_VERIFIED',
            profile=args.profile,
            expected_boot=binding['expected_boot'], key_extracted=False,
            hardware_access=False, attempt_reserved=False)))
        return
    sys.path.insert(0, str(root / '.firmware-tools/littlefs-review'))
    import littlefs
    if not Path(littlefs.__file__).resolve().is_relative_to((root / '.firmware-tools/littlefs-review').resolve()):
        raise ValueError('Unexpected LittleFS implementation')
    key = read_hold_key(candidate, littlefs)
    result = run_supported_recovery(root, startup_export_id=args.startup_export,
                                    key=key, authorized_recovery=True, profile=args.profile, **extra)
    print(json.dumps(result))


if __name__ == '__main__': main()
