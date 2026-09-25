"""Preflight or run one fixed return from the measured offset shoulder pose.

The native owner independently acquires fresh seven-servo feedback. This
launcher neither auto-retries nor treats an encoder return as tip clearance.
"""

import argparse
import json
import os
from pathlib import Path

from observe_r33_campaign import load_reviewed_key
from rocell.application.characterization_http import CharacterizationHTTP
from rocell.application.first_motion_contract import canonical
from rocell.application.park_reanchor_host import ParkReanchorHost
from rocell.application.park_reanchor_plan import plan_park_reanchor
from rocell.application.physical_onboarding_durability import read_bounded_regular_file
from rocell.application.pose_observation_export import replay_pose_observation
from rocell.application.product_ghost_export_review import _read
from rocell.application.supported_recovery_installation import review_recovery_startup
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter


def preflight(root, startup_export, pose_export):
    root = Path(root).resolve()
    binding = review_recovery_startup(root, startup_export, revision=57)
    exports = root / 'runs/wizard-exports'
    boot = binding['expected_boot']
    claim = exports / f'r57-park-return-{boot}.json'
    if claim.exists():
        raise ValueError('Return attempt already claimed on boot')
    if (exports / f'pose-observation-{boot}.json').exists():
        raise ValueError('Current boot reserved by pose capture; fresh startup required')
    if (exports / f'r57-auth-gate-used-{boot}.json').exists():
        raise ValueError('Authentication gate already used; fresh startup required')
    raw, _ = _read(exports, pose_export, 'attachment-pose-raw.json')
    source_boot = raw['subject']['expected_boot']
    if source_boot == boot:
        raise ValueError('Same-boot pose capture owns the diagnostic bus')
    observation = replay_pose_observation(exports, pose_export)
    if observation['replay_verified'] is not True:
        raise ValueError('Pose export did not replay')
    source_claim = exports / f'pose-observation-{source_boot}.json'
    if not source_claim.exists():
        raise ValueError('One-use source-boot pose claim required')
    retained = json.loads(read_bounded_regular_file(source_claim,
                                                    maximum_bytes=2048))
    if canonical(retained) != canonical({
            'expected_boot': source_boot,
            'expected_id': raw['subject']['expected_id'],
            'retry_allowed': False}):
        raise ValueError('Source pose claim differs')
    if any((exports / f'{prefix}-{boot}.json').exists() for prefix in (
            'r54-reanchor', 'r55-park-step', 'r56-park-step',
            'r57-park-step')):
        raise ValueError('Boot claimed by another movement route')
    plan = plan_park_reanchor(observation['assessment'],
                              observation_boot=source_boot,
                              observation_export_id=pose_export)
    plan['observation_bundle_sha256'] = observation['raw_bundle_sha256']
    return binding, exports, claim, plan


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--startup-export', required=True)
    parser.add_argument('--pose-export', required=True)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--preflight-only', action='store_true')
    mode.add_argument('--authorized-once', action='store_true')
    parser.add_argument('--clearance-confirmed', action='store_true',
                        help='Human-confirmed clear tool path; required for live return')
    args = parser.parse_args(argv)
    root = Path(__file__).resolve().parents[1]
    binding, exports, claim, plan = preflight(root, args.startup_export,
                                               args.pose_export)
    if args.preflight_only:
        print(json.dumps({'status': 'R57_PARK_RETURN_BINDING_VERIFIED',
                          'boot': binding['expected_boot'],
                          'target_goals': plan['target_goals'],
                          'hardware_access': False,
                          'movement_authorized': False}))
        return
    if not args.clearance_confirmed:
        raise ValueError('Live return requires current tool-path clearance confirmation')
    key = load_reviewed_key(root)
    WizardDiagnosticExporter(exports).prepare(create=True)
    # Reserve before the first network command. An uncertain response can
    # never be retried by starting this CLI again on the same boot.
    with claim.open('x', encoding='utf-8') as stream:
        json.dump({'boot': binding['expected_boot'],
                   'startup_export': args.startup_export,
                   'pose_export': args.pose_export,
                   'target_goals': plan['target_goals'],
                   'operator_clearance_confirmed': True,
                   'scope': 'one-fixed-park-return'}, stream)
        stream.flush()
        os.fsync(stream.fileno())
    client = CharacterizationHTTP(binding['address'], key=key,
                                  boot=binding['expected_boot'])
    host = ParkReanchorHost(client, export_root=exports,
                            boot=binding['expected_boot'], plan=plan)
    result = host.run_once()
    print(json.dumps({'status': 'PARK_RETURN_RECORDED',
                      'export': result['export'],
                      'assessment': result['assessment'],
                      'physical_clearance_proven': False,
                      'continuation_authorized': False}))


if __name__ == '__main__':
    main()
