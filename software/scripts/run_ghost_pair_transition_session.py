"""Run one frozen r53 ghost-pair session after reviewed startup and clearance."""
import argparse
import json
import os
from pathlib import Path

from observe_r33_campaign import load_reviewed_key
from rocell.application.characterization_http import CharacterizationHTTP
from rocell.application.characterization_recovery_http import CharacterizationRecoveryHTTP
from rocell.application.ghost_pair_transition_campaign import plan_ghost_pair_transition_campaign
from rocell.application.ghost_pair_transition_runner import GhostPairTransitionRunner
from rocell.application.product_ghost_export_review import _read
from rocell.application.supported_recovery_installation import review_recovery_startup
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter


REVISION=53
PLAN_EXPORT='wizard-20260921T034947657070Z-49435f72783047f9bd6aba05a46bf65c'


def preflight(root,startup_export,session_index):
    """Bind an unused boot and exact plan without network or movement access."""
    if session_index not in (1,2,3):
        raise ValueError('Session index must be 1, 2, or 3')
    binding=review_recovery_startup(root,startup_export,revision=REVISION)
    exports=root/'runs/wizard-exports'
    boot=binding['expected_boot']
    claim=exports/f'r53-session-{session_index}-capture-{boot}.json'
    # The read-only preparation consumes the controller's authenticated
    # sequence and NEW state. This runner owns a fresh sequence from zero and
    # performs its own reference review before its first target write.
    if ((exports/f'r53-capture-{boot}.json').exists() or
            any(exports.glob(f'r53-session-*-capture-{boot}.json')) or
            (exports/f'pose-observation-{boot}.json').exists()):
        raise ValueError('Boot already prepared or reserved; fresh startup required')
    saved,_=_read(exports,PLAN_EXPORT,'attachment-ghost-pair-transition-campaign-plan.json')
    expected=plan_ghost_pair_transition_campaign()
    if saved!=expected:
        raise ValueError('Frozen ghost-pair transition plan binding differs')
    binding['transition_plan']=expected
    return binding,exports,claim


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--startup-export',required=True)
    parser.add_argument('--session-index',type=int,required=True)
    mode=parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--preflight-only',action='store_true')
    mode.add_argument('--authorized-fixed-ghost-pair-clearance-confirmed',action='store_true')
    args=parser.parse_args()
    root=Path(__file__).resolve().parents[1]
    binding,exports,claim=preflight(root,args.startup_export,args.session_index)
    if args.preflight_only:
        print(json.dumps({'status':'GHOST_PAIR_BINDING_VERIFIED','revision':REVISION,
            'session_index':args.session_index,'hardware_access':False,
            'movement_authorized':False}))
        return
    key=load_reviewed_key(root)
    WizardDiagnosticExporter(exports).prepare(create=True)
    with claim.open('x',encoding='utf-8') as stream:
        json.dump({'boot':binding['expected_boot'],'startup_export':args.startup_export,
            'session_index':args.session_index,'scope':'fixed-ghost-pair-transition-session',
            'plan_sha256':binding['transition_plan']['plan_sha256']},stream)
        stream.flush()
        os.fsync(stream.fileno())
    client=CharacterizationHTTP(binding['address'],key=key,boot=binding['expected_boot'])

    def recovery(campaign):
        return CharacterizationRecoveryHTTP(binding['address'],key=key,
            boot=binding['expected_boot'],campaign=campaign)

    result=GhostPairTransitionRunner(client,exports,key=key,boot=binding['expected_boot'],
        recovery_factory=recovery).run(motion_admitted=True)
    print(json.dumps({'export_path':result['export_path'],
        'session_export':result.get('mapping_export'),
        'status':result['report']['status'],'session_index':args.session_index,
        'error':result['report'].get('error_message')}))
    if result['report']['status']!='COMPLETE':
        raise SystemExit(1)


if __name__=='__main__':
    main()
