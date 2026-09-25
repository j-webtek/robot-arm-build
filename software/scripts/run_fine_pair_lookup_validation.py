"""Run the exact r50 fine-endpoint repeat-validation batch after startup."""
import argparse,json,os
from pathlib import Path

from observe_r33_campaign import load_reviewed_key
from rocell.application.characterization_http import CharacterizationHTTP
from rocell.application.characterization_recovery_http import CharacterizationRecoveryHTTP
from rocell.application.fine_pair_lookup_runner import FinePairLookupRunner
from rocell.application.fine_pair_lookup_validation import plan_fine_lookup_validation
from rocell.application.product_ghost_export_review import _read
from rocell.application.supported_recovery_installation import review_recovery_startup
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter

REVISION=50
PLAN_EXPORT='wizard-20260920T225134995939Z-bb6fae52d11a4f168f7d09a627e31165'


def preflight(root,startup_export):
    binding=review_recovery_startup(root,startup_export,revision=REVISION)
    exports=root/'runs/wizard-exports';claim=exports/f'r{REVISION}-capture-{binding["expected_boot"]}.json'
    if claim.exists():raise ValueError('Boot already reserved; no reuse or automatic restart')
    if (exports/f'pose-observation-{binding["expected_boot"]}.json').exists():
        raise ValueError('Boot reserved by pose observation')
    saved,_=_read(exports,PLAN_EXPORT,'attachment-fine-pair-lookup-validation-plan.json')
    expected=plan_fine_lookup_validation()
    if saved!=expected:raise ValueError('Frozen fine lookup plan binding differs')
    binding['mapping_plan']=expected
    return binding,exports,claim


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--startup-export',required=True)
    mode=parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--preflight-only',action='store_true')
    mode.add_argument('--authorized-fixed-fine-lookup-clearance-confirmed',action='store_true')
    args=parser.parse_args();root=Path(__file__).resolve().parents[1]
    binding,exports,claim=preflight(root,args.startup_export)
    if args.preflight_only:
        print(json.dumps({'status':'LOCAL_BINDING_VERIFIED','hardware_access':False,
                          'movement_authorized':False,'revision':REVISION}));return
    key=load_reviewed_key(root);WizardDiagnosticExporter(exports).prepare(create=True)
    with claim.open('x',encoding='utf-8') as stream:
        json.dump({'boot':binding['expected_boot'],'startup_export':args.startup_export,
                   'scope':'fixed-fine-pair-lookup-validation',
                   'plan_sha256':binding['mapping_plan']['plan_sha256']},stream)
        stream.flush();os.fsync(stream.fileno())
    client=CharacterizationHTTP(binding['address'],key=key,boot=binding['expected_boot'])
    def recovery(campaign):
        return CharacterizationRecoveryHTTP(binding['address'],key=key,
            boot=binding['expected_boot'],campaign=campaign)
    result=FinePairLookupRunner(client,exports,key=key,boot=binding['expected_boot'],
                                recovery_factory=recovery).run(motion_admitted=True)
    print(json.dumps({'export_path':result['export_path'],'mapping_export':result.get('mapping_export'),
                      'status':result['report']['status'],'error':result['report'].get('error_message')}))
    if result['report']['status']!='COMPLETE':raise SystemExit(1)


if __name__=='__main__':main()
