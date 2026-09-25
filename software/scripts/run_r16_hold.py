"""One ordinary r16 hold from a fresh startup receipt; no restart or pair."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

from provision_startup_r6 import check_private_acl
from provision_hold_r7 import read_hold_key
from rocell.application.r10_provisioned_evidence import CANDIDATE
from rocell.application.r16_hold_launch import review_r16_hold_launch, run_r16_hold
from rocell.providers.windows.diagnostic_image_store import load_image


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--startup-export', required=True)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument('--preflight-only', action='store_true')
    modes.add_argument('--authorized-powered-hold', action='store_true')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    binding, _ = review_r16_hold_launch(root, args.startup_export)
    private = root / 'private-backups/controller-20260918-session1'
    check_private_acl(private)
    candidate = load_image(private / 'pair-r10-settings-candidate.dpapi')
    if len(candidate) != 0x160000 or hashlib.sha256(candidate).hexdigest() != CANDIDATE:
        raise ValueError('Retained key-source identity changed')
    if args.preflight_only:
        print(json.dumps(dict(status='LOCAL_R16_HOLD_PREFLIGHT_VERIFIED',
            expected_boot=binding['expected_boot'], hardware_access=False,
            key_extracted=False, attempt_reserved=False)))
        return
    sys.path.insert(0, str(root / '.firmware-tools/littlefs-review'))
    import littlefs
    if not Path(littlefs.__file__).resolve().is_relative_to((root / '.firmware-tools/littlefs-review').resolve()):
        raise ValueError('Unexpected LittleFS implementation')
    key = read_hold_key(candidate, littlefs)
    print(json.dumps(run_r16_hold(root, startup_export_id=args.startup_export,
                                 key=key, authorized_powered_hold=True)))


if __name__ == '__main__':
    main()
