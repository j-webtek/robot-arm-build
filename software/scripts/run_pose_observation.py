"""Receipt-bound pose acquisition; no installation, reset or movement."""
import argparse
import hashlib
import json
from pathlib import Path
from rocell.application.supported_recovery_installation import review_recovery_startup
from rocell.application.hold_transport_export import capture_hold_transport
from rocell.application.hold_transport_snapshot import HoldHTTPReader
from rocell.application.pose_observation_capture import capture_pose
from rocell.application.observed_pose_installation import review_observed_startup


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--startup-export',required=True)
    parser.add_argument('--revision',type=int,choices=(20,21,24,26,29,44,45,53,54,55,56,57,58,60,75,77,78))
    parser.add_argument('--stage-export')
    parser.add_argument('--installation-export')
    mode=parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--preflight-only',action='store_true')
    mode.add_argument('--authorized-observation',action='store_true')
    args=parser.parse_args(argv);root=Path(__file__).resolve().parents[1]
    if bool(args.stage_export) != bool(args.installation_export):
        parser.error('Stage and installation exports must be provided together')
    # r21 must bind the installed observed-pose settings, not just an app receipt.
    # This verifies historical provenance; the live idle check below is separate.
    revision=args.revision if args.revision is not None else (21 if args.stage_export else 20)
    if bool(args.stage_export)!=(revision==21):
        parser.error('Observed-pose settings receipts apply to r21 only and are required for r21')
    if revision==21:
        binding=review_observed_startup(root,startup_export=args.startup_export,
            stage_export=args.stage_export,installation_export=args.installation_export)
    else:
        binding=review_recovery_startup(root,args.startup_export,revision=revision)
    exports=root/'runs/wizard-exports';boot=binding['expected_boot']
    if (exports/('pose-observation-'+boot+'.json')).exists():
        raise ValueError('Observation attempt consumed; no retry')
    if revision in (53,54,55,56,57,58,60) and ((exports/f'r53-capture-{boot}.json').exists() or
                                 any(exports.glob(f'r53-session-*-capture-{boot}.json')) or
                                 (exports/f'r54-reanchor-{boot}.json').exists() or
                                 (exports/f'r55-park-step-{boot}.json').exists() or
                                 (exports/f'r56-park-step-{boot}.json').exists() or
                                 (exports/f'r57-park-return-{boot}.json').exists() or
                                 (exports/f'r58-visible-step-{boot}.json').exists() or
                                 (exports/f'r60-visible-step-{boot}.json').exists()):
        raise ValueError('Boot already claimed by a campaign or re-anchor; fresh idle startup required')
    # Known local owners invalidate admission even before touching the device.
    for name in ('shoulder-session-'+boot, 'first-hold-trial-'+boot, 'supported-recovery-trial-'+boot,
                 'held-pair-trial-'+hashlib.sha256(boot.encode('ascii')).hexdigest()):
        if (exports/(name+'.json')).exists():
            raise ValueError('Boot already used for actuation; fresh idle startup required')
    if args.preflight_only:
        print(json.dumps(dict(status=f'LOCAL_R{revision}_POSE_PREFLIGHT_VERIFIED',expected_boot=boot,
            hardware_access=False,motion_authorized=False,current_pose_verified=False)));return
    before=capture_hold_transport(exports,HoldHTTPReader(binding['address']),expected_boot=boot)
    status=before['summary'].get('status',{})
    if (before['summary']['category']!='TRANSPORT_CAPTURED' or status.get('state')!='IDLE' or
        status.get('reason')!='NOT_CONFIGURED' or status.get('records')!=0 or status.get('storage_fault') is not False):
        raise ValueError('Fresh same-boot idle state required')
    result=capture_pose(exports,address=binding['address'],expected_boot=boot,
        scan_id=f'r{revision}-pose-1',authorized=True)
    print(json.dumps(result))


if __name__=='__main__':main()
