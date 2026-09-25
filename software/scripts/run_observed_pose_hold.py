"""One receipt-bound ordinary hold; no startup, recovery, retry or pair."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
from rocell.application.observed_pose_hold import review_observed_hold, run_observed_hold


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('startup-export','stage-export','installation-export'):
        parser.add_argument('--'+name,required=True)
    modes=parser.add_mutually_exclusive_group(required=True)
    modes.add_argument('--preflight-only',action='store_true')
    modes.add_argument('--authorized-powered-hold',action='store_true')
    args=parser.parse_args();root=Path(__file__).resolve().parents[1]
    links=dict(startup_export=args.startup_export,stage_export=args.stage_export,
               installation_export=args.installation_export)
    binding,_=review_observed_hold(root,**links)
    if args.preflight_only:
        print(json.dumps(dict(status='LOCAL_OBSERVED_HOLD_PREFLIGHT_VERIFIED',
            expected_boot=binding['expected_boot'],hardware_access=False,key_extracted=False)))
        return
    from provision_startup_r6 import check_private_acl
    from provision_hold_r7 import read_hold_key
    from rocell.providers.windows.diagnostic_image_store import load_image
    private=root/'private-backups/controller-20260918-session1';check_private_acl(private)
    image=load_image(private/'observed-pose-plus10-candidate.dpapi')
    if len(image)!=0x160000 or hashlib.sha256(image).hexdigest()!=binding['observed_pose_installation']['candidate_sha256']:
        raise ValueError('Installed key-source identity differs')
    sys.path.insert(0,str(root/'.firmware-tools/littlefs-review'))
    import littlefs
    if not Path(littlefs.__file__).resolve().is_relative_to((root/'.firmware-tools/littlefs-review').resolve()):
        raise ValueError('Unexpected filesystem implementation')
    key=read_hold_key(image,littlefs)
    print(json.dumps(run_observed_hold(root,key=key,approved=True,**links)))


if __name__=='__main__':main()
