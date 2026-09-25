"""Prepare offline or run one receipt-bound r16 pair; never reset or install."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

from provision_startup_r6 import check_private_acl
from provision_hold_r7 import read_hold_key
from rocell.application.r10_provisioned_evidence import CANDIDATE
from rocell.application.r16_pair_launch import prepare_r16_pair, review_r16_pair, run_r16_pair
from rocell.providers.windows.diagnostic_image_store import load_image


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--startup-export', required=True)
    parser.add_argument('--hold-export')
    parser.add_argument('--preparation-export')
    parser.add_argument('--negative-installation-export')
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument('--prepare-only', action='store_true')
    modes.add_argument('--preflight-only', action='store_true')
    modes.add_argument('--authorized-powered-pair', action='store_true')
    args = parser.parse_args(argv)
    root = Path(__file__).resolve().parents[1]
    if args.prepare_only:
        if not args.hold_export or args.preparation_export:
            parser.error('Preparation requires only --hold-export as its source')
        result = prepare_r16_pair(root, startup_export_id=args.startup_export,
                                 hold_export_id=args.hold_export,
                                 offset_counts=-6 if args.negative_installation_export else 6,
                                 negative_installation_id=args.negative_installation_export)
        print(json.dumps(result))
        return
    if not args.preparation_export or args.hold_export:
        parser.error('Preflight/execution requires only --preparation-export as its source')
    binding, source = review_r16_pair(root, args.startup_export, args.preparation_export,args.negative_installation_export)
    private = root / 'private-backups/controller-20260918-session1'
    check_private_acl(private)
    image = load_image(private / 'pair-r10-settings-candidate.dpapi')
    if len(image) != 0x160000 or hashlib.sha256(image).hexdigest() != CANDIDATE:
        raise ValueError('Retained key-source identity changed')
    if args.preflight_only:
        print(json.dumps(dict(status='LOCAL_R16_PAIR_PREFLIGHT_VERIFIED',
            expected_boot=binding['expected_boot'], preparation_export_id=args.preparation_export,
            illustrative_targets=source['preparation']['illustrative_targets'],
            hardware_access=False, key_extracted=False, attempt_reserved=False)))
        return
    sys.path.insert(0, str(root / '.firmware-tools/littlefs-review'))
    import littlefs
    if not Path(littlefs.__file__).resolve().is_relative_to((root / '.firmware-tools/littlefs-review').resolve()):
        raise ValueError('Unexpected LittleFS implementation')
    key = read_hold_key(image, littlefs)
    print(json.dumps(run_r16_pair(root, startup_export_id=args.startup_export,
        preparation_id=args.preparation_export, key=key, approved=True,
        negative_installation_id=args.negative_installation_export)))


if __name__ == '__main__':
    main()
