"""One explicitly admitted r38 six-leg repeatability campaign; no reset or retry.

Includes planned reversals, but no extra return or follow-on campaign.

Preflight is local-only. A previously prepared boot cannot be reused because its
authenticated sequence and short-lived challenge belong to that earlier session.
"""
import argparse
import json
import os
from pathlib import Path
from observe_r33_campaign import load_reviewed_key
from rocell.application.supported_recovery_installation import review_recovery_startup
from rocell.application.characterization_http import CharacterizationHTTP
from rocell.application.characterization_repeatability_runner import RepeatabilityRunner
from rocell.application.characterization_recovery_http import CharacterizationRecoveryHTTP
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter


def preflight(root, startup_export):
    binding=review_recovery_startup(root,startup_export,revision=38)
    exports=root/'runs/wizard-exports'
    boot=binding['expected_boot']
    claim=exports/f'r38-capture-{boot}.json'
    if claim.exists():
        raise ValueError('Boot already reserved; no reuse or automatic restart')
    from rocell.application.product_ghost_export_review import _read
    proposal,_=_read(exports,'wizard-20260920T170731881182Z-5aa06999afa04b93a1c450b826e54391',
                     'attachment-repeatability-plan.json')
    frozen=proposal['frozen_models']
    if frozen['sha256']!='963df1b4975ca385e6b8d9cd9509695fdfa4838f0cab9bcde9444e28c28452e5':
        raise ValueError('Unreviewed model parameters')
    from rocell.application.shoulder_repeatability_plan import predict
    predict(frozen,target=(2389,1725),before=(2391,1724),direction=1)
    binding['frozen_models']=frozen
    return binding, exports, claim


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--startup-export',required=True)
    mode=parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--preflight-only',action='store_true')
    mode.add_argument('--authorized-six-leg-campaign-clearance-confirmed',action='store_true')
    args=parser.parse_args()
    root=Path(__file__).resolve().parents[1]
    binding,exports,claim=preflight(root,args.startup_export)
    if args.preflight_only:
        print(json.dumps(dict(status='LOCAL_BINDING_VERIFIED',hardware_access=False,
                              fresh_device_state_verified=False,movement_authorized=False)))
        return
    key=load_reviewed_key(root)
    WizardDiagnosticExporter(exports).prepare(create=True)
    # Same atomic namespace as read-only preparation: neither process may reuse
    # a boot reserved by the other. Preserve claims after all failures.
    with claim.open('x',encoding='utf-8') as stream:
        json.dump(dict(boot=binding['expected_boot'],startup_export=args.startup_export,
                       scope='six-leg-repeatability-campaign',frozen_model_sha256=binding['frozen_models']['sha256']),stream)
        stream.flush();os.fsync(stream.fileno())
    client=CharacterizationHTTP(binding['address'],key=key,boot=binding['expected_boot'])
    def recovery(campaign):
        return CharacterizationRecoveryHTTP(binding['address'],key=key,
            boot=binding['expected_boot'],campaign=campaign)
    result=RepeatabilityRunner(client,exports,key=key,boot=binding['expected_boot'],
                         recovery_factory=recovery,frozen_models=binding['frozen_models']).run(
        motion_admitted=True)
    print(json.dumps(dict(export_path=result['export_path'],status=result['report']['status'],
                          error=result['report'].get('error_message'))))
    if result['report']['status']!='COMPLETE':
        raise SystemExit(1)


if __name__=='__main__':main()
