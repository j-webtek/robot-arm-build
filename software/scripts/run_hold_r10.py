"""One r10 hold using verified pair provisioning; no reset, write or retry."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

from provision_startup_r6 import check_private_acl
from provision_hold_r7 import read_hold_key
from rocell.application.first_motion_contract import canonical
from rocell.application.r10_provisioned_evidence import review_provisioned_r10, BOOT, CANDIDATE, SOURCE, POLICY, ADDRESS
from rocell.providers.windows.diagnostic_image_store import load_image


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument('--preflight-only', action='store_true')
    modes.add_argument('--authorized-powered-hold', action='store_true')
    parser.add_argument('--expected-boot')
    parser.add_argument('--revision',type=int,choices=(10,11,12,13),default=10)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    evidence = review_provisioned_r10(root,revision=args.revision)
    boot = evidence['expected_boot']
    if args.authorized_powered_hold and args.expected_boot != boot:
        parser.error('Exact installed startup boot required')
    private = root/'private-backups/controller-20260918-session1'
    check_private_acl(private)
    if (root/'runs/wizard-exports'/('first-hold-trial-'+boot+'.json')).exists():
        raise ValueError('Hold attempt already consumed; no automatic recovery')
    candidate = load_image(private/'pair-r10-settings-candidate.dpapi')
    source = load_image(private/'pair-r10-settings-prewrite-source.dpapi')
    for data, expected in ((candidate,CANDIDATE),(source,SOURCE)):
        if len(data)!=0x160000 or hashlib.sha256(data).hexdigest()!=expected:
            raise ValueError('Private candidate/recovery identity differs')
    policy = canonical(json.loads((root/'docs/hold-r7-supported-pose-draft.json').read_bytes()))
    if hashlib.sha256(policy).hexdigest()!=POLICY:
        raise ValueError('Retained hold policy changed')
    if args.preflight_only:
        print(json.dumps(dict(status=f'LOCAL_R{args.revision}_HOLD_PREFLIGHT_VERIFIED', evidence=evidence,
            key_extracted=False, attempt_reserved=False)))
        return
    sys.path.insert(0,str(root/'.firmware-tools/littlefs-review'))
    import littlefs
    if not Path(littlefs.__file__).resolve().is_relative_to((root/'.firmware-tools/littlefs-review').resolve()):
        raise ValueError('Unexpected LittleFS implementation')
    key = read_hold_key(candidate,littlefs)
    from rocell.application.hold_first_trial_run import run_first_hold
    result = run_first_hold(root/'runs/wizard-exports', configuration=json.loads(policy),
        expected_boot=boot, key=key, address=ADDRESS, authorized_powered_hold=True)
    print(json.dumps(result))


if __name__=='__main__':
    main()
