"""Preflight or run one fixed, larger paired-shoulder step on corrected r60.

The command is fixed at 2413/1701, permits one write and never retries or
returns automatically.  Construction and preflight are inert.
"""

import argparse
import json
import os
from pathlib import Path

from observe_r33_campaign import load_reviewed_key
from rocell.application.characterization_http import CharacterizationHTTP
from rocell.application.first_motion_contract import canonical
from rocell.application.park_reanchor_host import ParkReanchorHost
from rocell.application.physical_onboarding_durability import read_bounded_regular_file
from rocell.application.pose_observation_export import replay_pose_observation
from rocell.application.product_ghost_export_review import _read
from rocell.application.supported_recovery_installation import review_recovery_startup
from rocell.application.visible_shoulder_step_plan import plan_visible_shoulder_step
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter


def preflight(root, startup_export, pose_export):
    root = Path(root).resolve()
    binding = review_recovery_startup(root, startup_export, revision=60)
    exports = root / 'runs/wizard-exports'
    boot = binding['expected_boot']
    claim = exports / f'r60-visible-step-{boot}.json'
    if claim.exists():
        raise ValueError('Visible step already claimed on boot')
    if (exports / f'pose-observation-{boot}.json').exists():
        raise ValueError('Current boot reserved by pose capture; fresh startup required')
    raw, _ = _read(exports, pose_export, 'attachment-pose-raw.json')
    source_boot = raw['subject']['expected_boot']
    if source_boot == boot:
        raise ValueError('Same-boot pose capture owns the diagnostic bus')
    observation = replay_pose_observation(exports, pose_export)
    if observation['replay_verified'] is not True:
        raise ValueError('Pose export did not replay')
    source_claim = exports / f'pose-observation-{source_boot}.json'
    retained = json.loads(read_bounded_regular_file(source_claim,
                                                    maximum_bytes=2048))
    if canonical(retained) != canonical({
            'expected_boot': source_boot,
            'expected_id': raw['subject']['expected_id'],
            'retry_allowed': False}):
        raise ValueError('Source pose claim differs')
    if any((exports / f'{prefix}-{boot}.json').exists() for prefix in (
            'r54-reanchor', 'r55-park-step', 'r56-park-step',
            'r57-park-return', 'r58-visible-step')):
        raise ValueError('Boot claimed by another movement route')
    plan = plan_visible_shoulder_step(
        observation['assessment'], observation_boot=source_boot,
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
    parser.add_argument('--clearance-confirmed', action='store_true')
    args = parser.parse_args(argv)
    root = Path(__file__).resolve().parents[1]
    binding, exports, claim, plan = preflight(root, args.startup_export,
                                               args.pose_export)
    if args.preflight_only:
        print(json.dumps({
            'status': 'R60_VISIBLE_STEP_BINDING_VERIFIED',
            'boot': binding['expected_boot'],
            'source_goals': plan['source_goals'][1:3],
            'target_goals': plan['target_goals'],
            'hardware_access': False, 'movement_authorized': False}))
        return
    if not args.clearance_confirmed:
        raise ValueError('Live visible step requires current path clearance confirmation')
    key = load_reviewed_key(root)
    WizardDiagnosticExporter(exports).prepare(create=True)
    with claim.open('x', encoding='utf-8') as stream:
        json.dump({'boot': binding['expected_boot'],
                   'startup_export': args.startup_export,
                   'pose_export': args.pose_export,
                   'target_goals': plan['target_goals'],
                   'operator_clearance_confirmed': True,
                   'scope': 'one-fixed-visible-shoulder-step'}, stream)
        stream.flush(); os.fsync(stream.fileno())
    client = CharacterizationHTTP(binding['address'], key=key,
                                  boot=binding['expected_boot'])
    host = ParkReanchorHost(client, export_root=exports,
                            boot=binding['expected_boot'], plan=plan)
    result = host.run_once()
    print(json.dumps({'status': 'VISIBLE_SHOULDER_STEP_RECORDED',
                      'export': result['export'],
                      'assessment': result['assessment'],
                      'physical_clearance_proven': False,
                      'continuation_authorized': False}))


if __name__ == '__main__':
    main()
