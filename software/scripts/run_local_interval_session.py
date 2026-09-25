"""Run one of three exact r51 local-interval sessions after reviewed startup."""
import argparse,json,os
from pathlib import Path

from observe_r33_campaign import load_reviewed_key
from rocell.application.characterization_http import CharacterizationHTTP
from rocell.application.characterization_recovery_http import CharacterizationRecoveryHTTP
from rocell.application.local_interval_campaign import plan_local_interval_campaign
from rocell.application.local_interval_runner import LocalIntervalRunner
from rocell.application.product_ghost_export_review import _read
from rocell.application.supported_recovery_installation import review_recovery_startup
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter

REVISION=51
PLAN_EXPORT='wizard-20260921T030720711609Z-dd03b9b60955416198ea6897c13a1216'


def preflight(root,startup_export,session_index):
    if session_index not in (1,2,3):raise ValueError('Session index must be 1, 2, or 3')
    binding=review_recovery_startup(root,startup_export,revision=REVISION)
    exports=root/'runs/wizard-exports';claim=exports/f'r51-session-{session_index}-capture-{binding["expected_boot"]}.json'
    if claim.exists() or (exports/f'pose-observation-{binding["expected_boot"]}.json').exists():
        raise ValueError('Boot already reserved')
    saved,_=_read(exports,PLAN_EXPORT,'attachment-local-interval-campaign-plan.json')
    expected=plan_local_interval_campaign()
    if saved!=expected:raise ValueError('Frozen local interval plan binding differs')
    binding['mapping_plan']=expected
    return binding,exports,claim


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--startup-export',required=True);parser.add_argument('--session-index',type=int,required=True)
    mode=parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--preflight-only',action='store_true')
    mode.add_argument('--authorized-fixed-local-interval-clearance-confirmed',action='store_true')
    args=parser.parse_args();root=Path(__file__).resolve().parents[1]
    binding,exports,claim=preflight(root,args.startup_export,args.session_index)
    if args.preflight_only:
        print(json.dumps({'status':'LOCAL_BINDING_VERIFIED','revision':REVISION,
            'session_index':args.session_index,'hardware_access':False,'movement_authorized':False}));return
    key=load_reviewed_key(root);WizardDiagnosticExporter(exports).prepare(create=True)
    with claim.open('x',encoding='utf-8') as stream:
        json.dump({'boot':binding['expected_boot'],'startup_export':args.startup_export,
            'session_index':args.session_index,'scope':'fixed-local-interval-session',
            'plan_sha256':binding['mapping_plan']['plan_sha256']},stream)
        stream.flush();os.fsync(stream.fileno())
    client=CharacterizationHTTP(binding['address'],key=key,boot=binding['expected_boot'])
    def recovery(campaign):return CharacterizationRecoveryHTTP(
        binding['address'],key=key,boot=binding['expected_boot'],campaign=campaign)
    result=LocalIntervalRunner(client,exports,key=key,boot=binding['expected_boot'],
        recovery_factory=recovery).run(motion_admitted=True)
    print(json.dumps({'export_path':result['export_path'],'mapping_export':result.get('mapping_export'),
        'status':result['report']['status'],'session_index':args.session_index,
        'error':result['report'].get('error_message')}))
    if result['report']['status']!='COMPLETE':raise SystemExit(1)


if __name__=='__main__':main()
