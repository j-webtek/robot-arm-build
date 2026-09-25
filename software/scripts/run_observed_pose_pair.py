"""Prepare/check offline, or execute one separately approved +10/return trial."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

from rocell.application.observed_pose_pair import (
    prepare_observed_pair, review_observed_pair, run_observed_pair,
)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('startup-export','stage-export','installation-export'):
        parser.add_argument('--'+name, required=True)
    parser.add_argument('--hold-export')
    parser.add_argument('--preparation-export')
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument('--prepare-only',action='store_true')
    modes.add_argument('--preflight-only',action='store_true')
    modes.add_argument('--authorized-powered-pair',action='store_true')
    args = parser.parse_args(argv)
    root = Path(__file__).resolve().parents[1]
    links = dict(startup_export=args.startup_export,stage_export=args.stage_export,
                 installation_export=args.installation_export)
    if args.prepare_only:
        if not args.hold_export or args.preparation_export:
            parser.error('Preparation requires only --hold-export as its source')
        print(json.dumps(prepare_observed_pair(root,hold_export=args.hold_export,**links)))
        return
    if not args.preparation_export or args.hold_export:
        parser.error('Preflight/execution requires only --preparation-export as its source')
    binding, source = review_observed_pair(root,preparation_export=args.preparation_export,**links)
    if args.preflight_only:
        print(json.dumps(dict(status='LOCAL_OBSERVED_PAIR_PREFLIGHT_VERIFIED',
            expected_boot=binding['expected_boot'],preparation_export_id=args.preparation_export,
            illustrative_targets=source['preparation']['illustrative_targets'],
            hardware_access=False,key_extracted=False,attempt_reserved=False)))
        return
    # Private key access occurs only after explicit execution and receipt review.
    from provision_startup_r6 import check_private_acl
    from provision_hold_r7 import read_hold_key
    from rocell.providers.windows.diagnostic_image_store import load_image
    private = root/'private-backups/controller-20260918-session1'
    check_private_acl(private)
    image = load_image(private/'observed-pose-plus10-candidate.dpapi')
    expected = binding['observed_pose_installation']['candidate_sha256']
    if len(image)!=0x160000 or hashlib.sha256(image).hexdigest()!=expected:
        raise ValueError('Installed candidate key-source identity differs')
    sys.path.insert(0,str(root/'.firmware-tools/littlefs-review'))
    import littlefs
    if not Path(littlefs.__file__).resolve().is_relative_to((root/'.firmware-tools/littlefs-review').resolve()):
        raise ValueError('Unexpected filesystem implementation')
    key = read_hold_key(image,littlefs)
    print(json.dumps(run_observed_pair(root,preparation_export=args.preparation_export,
                                       key=key,approved=True,**links)))


if __name__=='__main__':
    main()
