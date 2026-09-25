"""Run one fixed follow-up campaign after reviewed installation and startup."""
import argparse,json,os
from pathlib import Path
from observe_r33_campaign import load_reviewed_key
from rocell.application.supported_recovery_installation import review_recovery_startup
from rocell.application.product_ghost_export_review import _read
from rocell.application.shoulder_repeatability_plan import predict
from rocell.application.next_validation_runner import NextValidationRunner,CONFIG
from rocell.application.characterization_http import CharacterizationHTTP
from rocell.application.characterization_recovery_http import CharacterizationRecoveryHTTP
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter

REVISIONS={'forward_repeat':41,'reverse_candidate':42,'reverse_control':43,
           'heldout_candidate':44,'heldout_control':45,
           'second_heldout_candidate':46,'second_heldout_control':47}
LEGACY_PLAN='wizard-20260920T190401776719Z-da3be81ec93e4e6299dad3dadcfe7c2c'
HELDOUT_PLAN='wizard-20260920T200421886717Z-b78da5a8c1c64ca0a661883a2cb52828'
SECOND_HELDOUT_PLAN='wizard-20260920T205018907434Z-55fca8d673974a429423f6606f6be19e'


def preflight(root,startup_export,variant):
    revision=REVISIONS[variant]
    binding=review_recovery_startup(root,startup_export,revision=revision)
    exports=root/'runs/wizard-exports';claim=exports/f'r{revision}-capture-{binding["expected_boot"]}.json'
    if claim.exists():raise ValueError('Boot already reserved; no reuse or automatic restart')
    pose_claim=exports/f'pose-observation-{binding["expected_boot"]}.json'
    if pose_claim.exists():
        raise ValueError('Boot reserved by pose observation; perform a separately authorized startup before campaign')
    second_heldout=variant.startswith('second_heldout_')
    heldout=variant.startswith('heldout_')
    plan_export=(SECOND_HELDOUT_PLAN if second_heldout else
                 HELDOUT_PLAN if heldout else LEGACY_PLAN)
    plan_attachment=('attachment-second-heldout-pair-plan.json' if second_heldout else
                     'attachment-heldout-pair-plan.json' if heldout else
                     'attachment-next-validation-plan.json')
    plan,_=_read(exports,plan_export,plan_attachment)
    proposal,_=_read(exports,'wizard-20260920T170731881182Z-5aa06999afa04b93a1c450b826e54391',
                     'attachment-repeatability-plan.json')
    frozen=proposal['frozen_models']
    if (plan['frozen_model_sha256']!=frozen['sha256'] or
        frozen['sha256']!='963df1b4975ca385e6b8d9cd9509695fdfa4838f0cab9bcde9444e28c28452e5'):
        raise ValueError('Validation model binding differs')
    expected=CONFIG[variant]['targets']
    plan_variant=(variant.removeprefix('second_heldout_') if second_heldout else
                  variant.removeprefix('heldout_') if heldout else variant)
    if plan[plan_variant]['manifest']['goals']!=expected:
        raise ValueError('Validation manifest binding differs')
    predict(frozen,target=expected[-1],before=CONFIG[variant]['trial_positions'],
            direction=CONFIG[variant]['direction'])
    binding['frozen_models']=frozen;binding['plan_export']=plan_export
    return binding,exports,claim


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--variant',required=True,choices=REVISIONS)
    parser.add_argument('--startup-export',required=True)
    mode=parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--preflight-only',action='store_true')
    mode.add_argument('--authorized-fixed-campaign-clearance-confirmed',action='store_true')
    args=parser.parse_args();root=Path(__file__).resolve().parents[1]
    binding,exports,claim=preflight(root,args.startup_export,args.variant)
    if args.preflight_only:
        print(json.dumps(dict(status='LOCAL_BINDING_VERIFIED',variant=args.variant,
            hardware_access=False,movement_authorized=False)));return
    key=load_reviewed_key(root);WizardDiagnosticExporter(exports).prepare(create=True)
    with claim.open('x',encoding='utf-8') as stream:
        json.dump(dict(boot=binding['expected_boot'],startup_export=args.startup_export,
            scope='next-validation-fixed-campaign',variant=args.variant,
            plan_export=binding['plan_export'],frozen_model_sha256=binding['frozen_models']['sha256']),stream)
        stream.flush();os.fsync(stream.fileno())
    client=CharacterizationHTTP(binding['address'],key=key,boot=binding['expected_boot'])
    def recovery(campaign):return CharacterizationRecoveryHTTP(binding['address'],key=key,
        boot=binding['expected_boot'],campaign=campaign)
    result=NextValidationRunner(client,exports,key=key,boot=binding['expected_boot'],
        variant=args.variant,frozen_models=binding['frozen_models'],recovery_factory=recovery).run(
        motion_admitted=True)
    print(json.dumps(dict(export_path=result['export_path'],status=result['report']['status'],
        trial_audit_export=result.get('trial_audit_export'),error=result['report'].get('error_message'))))
    if result['report']['status']!='COMPLETE':raise SystemExit(1)


if __name__=='__main__':main()
