"""One authenticated measured-T1-to-P1 movement on reviewed r63 startup.

No retry, return, other pose, settings change or startup is performed here.
"""
import argparse
import json
import os
from pathlib import Path

from observe_r33_campaign import load_reviewed_key
from rocell.application.characterization_http import CharacterizationHTTP
from rocell.application.first_motion_contract import canonical
from rocell.application.hold_transport_snapshot import HoldHTTPReader,STATUS
from rocell.application.large_pose_lift_record import assess_large_pose_lift_record
from rocell.application.large_pose_relief_host import LargePoseReliefHost
from rocell.application.product_ghost_export_review import _read
from rocell.application.supported_recovery_installation import review_recovery_startup
from rocell.application.wizard_diagnostic_coordinator import decode_diagnostic_json
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter,verify_export


SOURCE='wizard-20260923T013000217507Z-65942c5e2f9b42f4b683f0fbf0a32455'


def preflight(root,startup_export):
    root=Path(root).resolve();exports=root/'runs/wizard-exports'
    binding=review_recovery_startup(root,startup_export,revision=63)
    assessment,digest=_read(exports,SOURCE,'attachment-large-pose-lift-assessment.json')
    source_dir=(exports/SOURCE).resolve()
    if not verify_export(source_dir)['valid']:
        raise ValueError('T1 source export invalid')
    raw=bytes.fromhex((source_dir/'attachment-large-pose-lift.hex.txt').read_text('ascii'))
    replay=assess_large_pose_lift_record(raw,expected_boot=assessment['boot'])
    if (assessment['status']!='T1_JOINT_ENDPOINT_MEASURED' or
            assessment['position_delta_counts']!=[0,-58,59,0,61,0,0] or
            canonical(assessment)!=canonical(replay)):
        raise ValueError('Reviewed T1 source evidence differs')
    boot=binding['expected_boot']
    claim=exports/f'r63-large-pose-relief-{boot}.json'
    if claim.exists() or (exports/f'pose-observation-{boot}.json').exists():
        raise ValueError('Boot already claimed by another operation')
    return binding,exports,claim,digest


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--startup-export',required=True)
    mode=parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--preflight-only',action='store_true')
    mode.add_argument('--authorized-once',action='store_true')
    args=parser.parse_args(argv)
    root=Path(__file__).resolve().parents[1]
    binding,exports,claim,source_digest=preflight(root,args.startup_export)
    if args.preflight_only:
        print(json.dumps(dict(status='R63_P1_BINDING_VERIFIED',boot=binding['expected_boot'],
                              source_export=SOURCE,hardware_access=False,
                              movement_authorized=False)))
        return
    reader=HoldHTTPReader(binding['address'])
    raw=reader(STATUS,maximum_bytes=512,timeout_seconds=3)
    status=decode_diagnostic_json(raw,maximum=512)
    if (status.get('instance_id')!=binding['expected_boot'] or
            status.get('state')!='IDLE' or status.get('storage_fault') is not False):
        raise ValueError('Reviewed r63 startup is no longer the idle live boot')
    key=load_reviewed_key(root)
    WizardDiagnosticExporter(exports).prepare(create=True)
    with claim.open('x',encoding='utf-8') as stream:
        json.dump(dict(boot=binding['expected_boot'],startup_export=args.startup_export,
                       source_export=SOURCE,source_digest=source_digest,
                       scope='one-T1-to-P1-only',retry_allowed=False),stream)
        stream.flush();os.fsync(stream.fileno())
    client=CharacterizationHTTP(binding['address'],key=key,boot=binding['expected_boot'])
    result=LargePoseReliefHost(client,export_root=exports,
                               boot=binding['expected_boot']).run_once()
    print(json.dumps(dict(status='P1_RESULT_RECORDED',**result)))


if __name__=='__main__':
    main()
