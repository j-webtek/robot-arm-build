"""Run at most one authenticated r54 fixed pair re-anchor on a fresh boot.

No automatic return, retry, torque change, ghost sequence, or contact action.
"""
import argparse
import json
import os
from pathlib import Path

from observe_r33_campaign import load_reviewed_key
from rocell.application.characterization_http import CharacterizationHTTP
from rocell.application.fixed_pair_reanchor import plan_fixed_pair_reanchor
from rocell.application.fixed_pair_reanchor_host import FixedPairReanchorHost
from rocell.application.product_ghost_export_review import _read
from rocell.application.supported_recovery_installation import review_recovery_startup
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter


# Frozen from the fresh r54 read-only seven-servo capture, not the older r53 boot.
PLAN_EXPORT = 'wizard-20260921T221915958401Z-02c0a7ba6b3f42e980a67f89b7ff80a4'


def preflight(root, startup_export):
    root = Path(root).resolve()
    binding = review_recovery_startup(root, startup_export, revision=54)
    exports = root / 'runs/wizard-exports'
    boot = binding['expected_boot']
    claim = exports / f'r54-reanchor-{boot}.json'
    if (claim.exists() or (exports/f'pose-observation-{boot}.json').exists() or
            any(exports.glob(f'r54-session-*-capture-{boot}.json'))):
        raise ValueError('r54 boot already claimed; separately reviewed startup required')
    saved, _ = _read(exports, PLAN_EXPORT, 'attachment-fixed-pair-reanchor-plan.json')
    expected = plan_fixed_pair_reanchor(exports, saved['source_export_id'])
    if saved != expected:
        raise ValueError('Frozen re-anchor plan or source capture changed')
    return binding, exports, claim, expected


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--startup-export', required=True)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--preflight-only', action='store_true')
    mode.add_argument('--authorized-once', action='store_true')
    args = parser.parse_args(argv)
    root = Path(__file__).resolve().parents[1]
    binding, exports, claim, plan = preflight(root, args.startup_export)
    if args.preflight_only:
        print(json.dumps(dict(status='R54_REANCHOR_BINDING_VERIFIED',
                              boot=binding['expected_boot'], hardware_access=False,
                              movement_authorized=False)))
        return
    key = load_reviewed_key(root)
    WizardDiagnosticExporter(exports).prepare(create=True)
    # Durable one-use claim precedes every network command. An uncertain write
    # cannot be retried by invoking this CLI again on the same boot.
    with claim.open('x', encoding='utf-8') as stream:
        json.dump(dict(boot=binding['expected_boot'], startup_export=args.startup_export,
                       plan_export=PLAN_EXPORT, scope='one-fixed-pair-reanchor'), stream)
        stream.flush()
        os.fsync(stream.fileno())
    client = CharacterizationHTTP(binding['address'], key=key,
                                  boot=binding['expected_boot'])
    host = FixedPairReanchorHost(client, export_root=exports,
                                 boot=binding['expected_boot'], plan=plan)
    result = host.run_once()
    print(json.dumps(dict(status='REANCHOR_VERIFIED', export=result['export'],
                          physical_motion_proven=False,
                          continuation_authorized=False)))


if __name__ == '__main__':
    main()
