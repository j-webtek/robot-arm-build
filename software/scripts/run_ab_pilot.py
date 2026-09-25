"""One fixed three-leg pilot, gated by reviewed installation/startup evidence.

Unreviewed revisions fail locally. This launcher never installs, resets, retries,
or switches a running controller's variant. Preflight never opens a connection.
"""
import argparse
import json
import os
from pathlib import Path
from observe_r33_campaign import load_reviewed_key
from rocell.application.supported_recovery_installation import review_recovery_startup
from rocell.application.product_ghost_export_review import _read
from rocell.application.shoulder_repeatability_plan import predict
from rocell.application.characterization_ab_runner import ABRunner
from rocell.application.characterization_http import CharacterizationHTTP
from rocell.application.characterization_recovery_http import CharacterizationRecoveryHTTP
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter

REVISIONS = {'control': 39, 'compensated': 40}


def preflight(root, startup_export, variant):
    revision = REVISIONS[variant]
    # Require reviewed binary, installation journal and exact startup together.
    # An available profile alone is insufficient. Never fall back to r38.
    binding = review_recovery_startup(root, startup_export, revision=revision)
    exports = root/'runs/wizard-exports'
    claim = exports/f'r{revision}-capture-{binding["expected_boot"]}.json'
    if claim.exists():
        raise ValueError('Boot already reserved; no reuse or automatic restart')
    proposal, _ = _read(exports,
        'wizard-20260920T170731881182Z-5aa06999afa04b93a1c450b826e54391',
        'attachment-repeatability-plan.json')
    frozen = proposal['frozen_models']
    if frozen['sha256'] != '963df1b4975ca385e6b8d9cd9509695fdfa4838f0cab9bcde9444e28c28452e5':
        raise ValueError('Unreviewed model parameters')
    predict(frozen, target=(2389,1725), before=(2391,1724), direction=1)
    binding['frozen_models'] = frozen
    return binding, exports, claim


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--variant', required=True, choices=REVISIONS)
    parser.add_argument('--startup-export', required=True)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--preflight-only', action='store_true')
    mode.add_argument('--authorized-three-leg-campaign-clearance-confirmed', action='store_true')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    binding, exports, claim = preflight(root, args.startup_export, args.variant)
    if args.preflight_only:
        print(json.dumps(dict(status='LOCAL_BINDING_VERIFIED', variant=args.variant,
            hardware_access=False, fresh_device_state_verified=False, movement_authorized=False)))
        return
    key = load_reviewed_key(root)
    WizardDiagnosticExporter(exports).prepare(create=True)
    with claim.open('x', encoding='utf-8') as stream:
        json.dump(dict(boot=binding['expected_boot'], startup_export=args.startup_export,
            scope='three-leg-ab-pilot', variant=args.variant,
            frozen_model_sha256=binding['frozen_models']['sha256']), stream)
        stream.flush(); os.fsync(stream.fileno())
    client = CharacterizationHTTP(binding['address'], key=key, boot=binding['expected_boot'])
    def recovery(campaign):
        return CharacterizationRecoveryHTTP(binding['address'], key=key,
            boot=binding['expected_boot'], campaign=campaign)
    result = ABRunner(client, exports, key=key, boot=binding['expected_boot'],
        variant=args.variant, frozen_models=binding['frozen_models'],
        recovery_factory=recovery).run(motion_admitted=True)
    print(json.dumps(dict(export_path=result['export_path'],
        status=result['report']['status'], trial_audit_export=result.get('trial_audit_export'),
        error=result['report'].get('error_message'))))
    if result['report']['status'] != 'COMPLETE':
        raise SystemExit(1)


if __name__ == '__main__':
    main()
