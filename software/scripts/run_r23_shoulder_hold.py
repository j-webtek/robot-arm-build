"""One approved r23 shoulder initialization only; no restart, lift or retry."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
from rocell.application.supported_recovery_installation import review_recovery_startup
from rocell.application.shoulder_session_http import ShoulderSessionHTTP
from rocell.application.shoulder_session_runner import run_shoulder_session


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--startup-export',required=True)
    parser.add_argument('--revision',type=int,choices=(23,24,25,26,27,28,29),default=23)
    mode=parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--preflight-only',action='store_true')
    mode.add_argument('--authorized-powered-hold',action='store_true')
    mode.add_argument('--authorized-shoulder-rise',action='store_true')
    mode.add_argument('--authorized-clearance-recovery',action='store_true')
    mode.add_argument('--authorized-stable-clearance-recovery',action='store_true')
    args=parser.parse_args();root=Path(__file__).resolve().parents[1]
    if not args.preflight_only and (args.authorized_shoulder_rise!=(args.revision==27)
            or args.authorized_clearance_recovery!=(args.revision==28)
            or args.authorized_stable_clearance_recovery!=(args.revision==29)):
        parser.error('Each movement requires its exact flag and reviewed revision')
    binding=review_recovery_startup(root,args.startup_export,revision=args.revision)
    exports=root/'runs/wizard-exports';boot=binding['expected_boot']
    claims=('shoulder-session-'+boot,'pose-observation-'+boot,'first-hold-trial-'+boot,
            'supported-recovery-trial-'+boot,'held-pair-trial-'+hashlib.sha256(boot.encode()).hexdigest())
    if any((exports/(name+'.json')).exists() for name in claims):
        raise ValueError('Boot already reserved; no retry')
    if args.preflight_only:
        print(json.dumps(dict(status=f'R{args.revision}_LOCAL_HOLD_PREFLIGHT_VERIFIED',expected_boot=boot,
            hardware_access=False,key_extracted=False,hold_started=False)));return
    from provision_startup_r6 import check_private_acl
    from provision_hold_r7 import read_hold_key
    from rocell.providers.windows.diagnostic_image_store import load_image
    private=root/'private-backups/controller-20260918-session1';check_private_acl(private)
    image=load_image(private/'observed-pose-plus10-candidate.dpapi')
    if len(image)!=0x160000 or hashlib.sha256(image).hexdigest()!='45320bab56ec1d8e889078a50e2aa0ef79d4d65c59e5dcb89c7a7880f08e7267':
        raise ValueError('Installed key-source identity differs')
    sys.path.insert(0,str(root/'.firmware-tools/littlefs-review'))
    import littlefs
    if not Path(littlefs.__file__).resolve().is_relative_to((root/'.firmware-tools/littlefs-review').resolve()):
        raise ValueError('Unexpected filesystem implementation')
    key=read_hold_key(image,littlefs)
    result=run_shoulder_session(exports,expected_boot=boot,key=key,
        exchange=ShoulderSessionHTTP(binding['address']),authorized=True,origin='DEVICE_CAPTURE',
        software_root=root,startup_export=args.startup_export,revision=args.revision,
        experiment='STABLE_CLEARANCE_RECOVERY' if args.revision==29 else 'CLEARANCE_RECOVERY' if args.revision==28 else 'SHOULDER_RISE' if args.revision==27 else 'POSE_PREPARATION' if args.revision==26 else 'MIXED_TARGET' if args.revision==25 else 'PAIR_HOLD')
    report=result['report']
    print(json.dumps(dict(export_path=result['export_path'],state=report['state'],
        record_count=len(report['records']),error_type=report.get('error_type'),
        lift_sent=(True if any(op.get('response',{}).get('event')=='SHOULDER_STEP_SENT'
                              for op in report['operations']) else None) if args.revision in (27,28,29) else False,
        retry=False)))


if __name__=='__main__':main()
