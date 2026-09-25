"""One authenticated P0-to-T1 movement on the reviewed r62 startup.

No retry, return, other pose, settings change, or startup is performed here.
"""
import argparse
import json
import os
from pathlib import Path

from observe_r33_campaign import load_reviewed_key
from rocell.application.characterization_http import CharacterizationHTTP
from rocell.application.hold_transport_snapshot import HoldHTTPReader, STATUS
from rocell.application.large_pose_lift_host import LargePoseLiftHost
from rocell.application.supported_recovery_installation import review_recovery_startup
from rocell.application.wizard_diagnostic_coordinator import decode_diagnostic_json
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter


def preflight(root, startup_export):
    root=Path(root).resolve()
    binding=review_recovery_startup(root,startup_export,revision=62)
    exports=root/'runs/wizard-exports'
    boot=binding['expected_boot']
    claim=exports/f'r62-large-pose-lift-{boot}.json'
    if claim.exists():
        raise ValueError('Large-pose T1 attempt already claimed on boot')
    if any((exports/name).exists() for name in (
            f'r62-auth-gate-used-{boot}.json',f'pose-observation-{boot}.json')):
        raise ValueError('Boot already claimed by another operation')
    return binding,exports,claim


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--startup-export',required=True)
    mode=parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--preflight-only',action='store_true')
    mode.add_argument('--authorized-once',action='store_true')
    args=parser.parse_args(argv)
    root=Path(__file__).resolve().parents[1]
    binding,exports,claim=preflight(root,args.startup_export)
    if args.preflight_only:
        print(json.dumps(dict(status='R62_T1_BINDING_VERIFIED',boot=binding['expected_boot'],
                              hardware_access=False,movement_authorized=False)))
        return
    # This unsigned status is a read-only identity check, not a source-pose
    # observation. The native owner independently acquires the fresh pose.
    reader=HoldHTTPReader(binding['address'])
    raw=reader(STATUS,maximum_bytes=512,timeout_seconds=3)
    status=decode_diagnostic_json(raw,maximum=512)
    if (status.get('instance_id')!=binding['expected_boot'] or
            status.get('state')!='IDLE' or status.get('storage_fault') is not False):
        raise ValueError('Reviewed r62 startup is no longer the idle live boot')
    key=load_reviewed_key(root)
    WizardDiagnosticExporter(exports).prepare(create=True)
    with claim.open('x',encoding='utf-8') as stream:
        json.dump(dict(boot=binding['expected_boot'],startup_export=args.startup_export,
                       scope='one-P0-to-T1-only',retry_allowed=False),stream)
        stream.flush();os.fsync(stream.fileno())
    client=CharacterizationHTTP(binding['address'],key=key,boot=binding['expected_boot'])
    result=LargePoseLiftHost(client,export_root=exports,
                             boot=binding['expected_boot']).run_once()
    print(json.dumps(dict(status='T1_RESULT_RECORDED',**result)))


if __name__=='__main__':
    main()
